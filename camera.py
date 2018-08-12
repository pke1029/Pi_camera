# pke1029
# July 2018

# google drive api library
from __future__ import print_function
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools
from apiclient.http import MediaFileUpload

# camera and other library
from picamera import PiCamera
from picamera.array import PiRGBArray
from time import sleep
from datetime import datetime
import os
import shutil
import config


def capture_image(camera, res):

    camera.resolution = res
    with PiRGBArray(camera) as stream:
        camera.exposure_mode = 'auto'
        camera.awb_mode = 'auto'
        camera.capture(stream, format='rgb')

        # return red value
        return stream.array[:, :, 0]


def motion_detect(camera, res, frequency, threshold, sensitivity):

    # initialize output
    motion = False
    # unpack res into height and width variables
    width, height = res[0], res[1]
    # take first picture
    data_old = capture_image(camera, res)
    # wile no motion , keep checking
    while motion is False:
        diff_count = 0
        # wait
        sleep(1 / frequency)
        # take another picture
        data_new = capture_image(camera, res)
        # compute difference for each pixel
        for w in range(width):
            for h in range(height):
                diff = abs(int(data_old[h][w]) - int(data_new[h][w]))
                # count pixel that changed
                if diff > threshold:
                    diff_count += 1
        # if number of pixel that changed is large, motion detected
            if diff_count > sensitivity:
                break
        if diff_count > sensitivity:
            motion = True
        # if not, overwrite old image with new image
        else:
            data_old = data_new

    return motion


def record_video(camera, res, duration, file_name):

    # set resolution
    camera.resolution = res
    # sett file name
    camera.start_recording(file_name)
    # wait for recording
    camera.wait_recording(duration)
    # end recording
    camera.stop_recording()


def authenticate():
    
    # authorization as owner
    SCOPES = 'https://www.googleapis.com/auth/drive'
    # store permission (credentials)
    store = file.Storage('credentials.json')
    # get credentials/token
    creds = store.get()
    # if there is no credentials, request one 
    if not creds or creds.invalid:
        flow = client.flow_from_clientsecrets('client_secret.json', SCOPES)
        creds = tools.run_flow(flow, store)
    # authenticate
    drive_service = build('drive', 'v3', http=creds.authorize(Http()))

    return drive_service


def get_folder_id(drive_service, folder_name):

    folder_id = False
    
    query1 = "name='" + folder_name + "'"

    response = drive_service.files().list(q=query1,
                                          fields='nextPageToken, files(id, name)').execute()
    items = response.get('files', [])
    if items:
        folder_id = items[0]['id']
    
    return folder_id


def create_folder(drive_service, folder_name):

    # folder info
    file_metadata = {'name': folder_name,
		     'mimeType': 'application/vnd.google-apps.folder'}
    # create folder
    file = drive_service.files().create(body=file_metadata,
					fields='id').execute()
    # get folder id
    folder_id = file.get('id')

    return folder_id


def upload_file(drive_service, file_name, folder_id, file_path, mimetype):

    # name of the file
    file_metadata = {'name': file_name,
		     'parents': [folder_id]}
    # make media
    media = MediaFileUpload(file_path,
    	                    mimetype=mimetype)
    # upload file
    file = drive_service.files().create(body=file_metadata,
    	                                media_body=media,
        	                        fields='id').execute()
    # get file id
    file_id = file.get('id')

    return file_id


def get_folder_list(text_file):
    
    if not os.path.isfile(text_file):
        folder_name = []

    else:
        with open(text_file, 'r') as f:
            folder_name = f.read()
            folder_name = folder_name.split('\n')

    return folder_name


def main():
    
    # parameters
    lo_res      = config.lo_res         # resolution for motion detect
    hi_res      = config.hi_res         # resolution for video recording
    frequency   = config.frequency      # frequency of motion detect (Hz)
    fps         = config.fps            # fps for video recording
    duration    = config.duration       # duration of recording
    threshold   = config.threshold      # difference in each pixel [0, 256]
    sensitivity = config.sensitivity    # difference in each frame [0, 128*96]
    log_day     = config.log_day        # number of days to keep the log of

    # authenticate google drive
    print('authenticating...', end='')
    drive_service = authenticate()
    print(' success')
    
    # initialize camera
    camera = PiCamera()
    camera.rotation = 0
    sleep(5)

    # get folder list
    text_file = 'folder_list.txt'
    folder_list = get_folder_list(text_file)
    
    while True:

        # check if there is motion
        print('dectecting motion...', end='')
        motion = motion_detect(camera, lo_res, frequency, threshold, sensitivity)

        if motion is True:

            # get current time
            now = datetime.now()
            print(' motion detected ' + str(now))
            
            folder_name = str(now.date())
            file_name = str(now.time()) + '.h264'

            # make a folder
            if not os.path.exists(folder_name):
                os.makedirs(folder_name)

            file_path = folder_name + '/' + file_name

            # record video
            print('recording...', end='')
            record_video(camera, hi_res, duration, file_path)
            print(' done')

            # check if folder on google drive
            folder_id = get_folder_id(drive_service, folder_name)
            
            # if not, create one
            if folder_id is False:
                folder_id = create_folder(drive_service, folder_name)
                # record folder name
                folder_list.append(folder_name)
                with open(text_file, 'a') as f:
                    f.write(folder_name + '\n')

            # upload video to drive
            print('uploading...', end='')
            upload_file(drive_service, file_name, folder_id, file_path, 'video/h264')
            print(' success')

            # check if too much log
            if len(folder_list) > log_day:
                print('deleting folder...', end='')
                # get folder name and id
                folder_name = folder_list.pop(0)
                folder_id = get_folder_id(drive_service, folder_name)
                # delete from drive
                drive_service.files().delete(fileId=folder_id).execute()
                # delete folder
                shutil.rmtree(folder_name)
                # remove from list and text file
                with open(text_file, 'w') as f:
                    f.writelines(folder_list)
                print(' success')


if __name__ == '__main__':
    
    try:
        main()
    finally:
        print('\nEnd of programme, developed by pke1029')
