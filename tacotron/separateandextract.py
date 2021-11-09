import io
import os
import moviepy.editor as mp
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from django.conf import settings
from google.cloud import storage
from google.cloud import speech

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credential_path

from voice.models import replaceAudio

min_silence_len = 300
silence_thresh = -40

duration = 500
frame_rate = 22050

def createDirectory(directory):
    try:
        if not os.path.exists(directory):
            os.makedirs(directory)
    except OSError: print("Error: Failed to create the directory.")

def match_target_amplitude(sound, target_dBFS):
    change_in_dBFS = target_dBFS - sound.dBFS
    return sound.apply_gain(change_in_dBFS)

def changeToWav(user_name, file):
    name = os.path.basename(file)
    path = settings.MEDIA_ROOT + "/replace_video/{}/{}".format(user_name, name)
    video = mp.VideoFileClip(path)

    name_str = name.split('.')[0]
    print(name_str)
    save_path = 'separated/{}/'.format(user_name)
    if not os.path.exists(save_path):
        os.makedirs(save_path)
    video.audio.write_audiofile('{}/{}{}.wav'.format(settings.MEDIA_ROOT, save_path, name_str))

    audio = '{}{}.wav'.format(save_path, name_str)
    # # DB 저장 코드 작성
    # form = replaceAudio.objects.get(uploader=user_name, name=name_str)
    # form.audio = audio
    # form.save()

    return audio


def SeparateAndExtract(user_name, audio):
    recognition = {}
    audio = settings.MEDIA_ROOT+"/{}".format(audio) #/home/threhe13/django/media/separated/admin/199716_1.wav

    name = os.path.basename(audio)
    audio_segment = AudioSegment.from_wav(audio)
    normalized_sound = match_target_amplitude(audio_segment, -20.0)
    #print('length : {}'.format(len(normalized_sound) / 1000))
    nonsilent_data = detect_nonsilent(normalized_sound, 300, -40, seek_step=1)

    front = AudioSegment.silent(duration=500, frame_rate=22050)
    end = AudioSegment.silent(duration=500, frame_rate=22050)

    path = 'divided_audio/{}/'.format(user_name)
    full_path = settings.MEDIA_ROOT+"/{}".format(path)
    if not os.path.exists(full_path):
        os.makedirs(full_path)

    # print("start / stop")
    for i, temps in enumerate(nonsilent_data):
        start, stop = [temp / 1000 for temp in temps]
        #print(start, stop)

        out_audio = audio_segment[max(start * 1000, 0):min(stop * 1000, len(audio_segment))]
        export = front + out_audio + end

        #분할된 파일 저장
        out_file_name = "{}_{}.wav".format(name.split('.')[0], i)
        out_file_path = full_path + out_file_name
        export.export(out_file_path, format='wav')

        #Google STT
        #upload_blob("django", out_file_path, user_name)  # user_name == admin
        text = tts(out_file_path)

        #save timestamp and text of divided audio
        # timestamp = {'timestamp': start, "text": text}
        recognition[str(round(start, 2))] = text
        #print('export complete {}'.format(out_file_path))

    return recognition
    #DB - script -> timestamp, text(google stt)

def tts(audio_path):
    # Instantiates a client
    client = speech.SpeechClient()

    # The name of the audio file to transcribe
    with io.open(audio_path, "rb") as audio_file:
        content = audio_file.read()
        audio = speech.RecognitionAudio(content=content)
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=44100,  # wav file = 44100
        language_code="ko-KR",
        audio_channel_count=2,  # wav file = 2 channel
    )

    # Detects speech in the audio file
    response = client.recognize(config=config, audio=audio)

    result_list = ""
    for result in response.results:
        result_list = result_list + result.alternatives[0].transcript

    return result_list

def upload_blob(bucket_name, source_file_name, destination_blob_name):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    file_name = "{}/{}".format(destination_blob_name, source_file_name)

    blob = bucket.blob(file_name)
    blob.upload_from_filename(source_file_name)