# -- coding: utf-8 --
"""
This is a demo for a voice biometrics application
"""

# ------------------------------------------------------------------------------------------------------------------------------------#
#                                                  Installing Packages Needed                                                         #
# ------------------------------------------------------------------------------------------------------------------------------------#


# This is used to dump the models into an object
import json
import base64
import pickle
import datetime
import os                                               # For creating directories
import shutil                                           # For deleting directories
# from collections import defaultdict

import matplotlib.pyplot as plt
import numpy
import scipy.cluster
import scipy.io.wavfile
# For the speech detection alogrithms
import speech_recognition
# For the fuzzy matching algorithms
from fuzzywuzzy import fuzz
# For using the MFCC feature selection
from python_speech_features import mfcc
# For generating random words
from random_words import RandomWords
from sklearn import preprocessing
# For using the Gausian Mixture Models
from sklearn.mixture import GaussianMixture
# random int string choosen from text file
from random import randint
# Speechpro libraries
from cloud_client.api.session_api import SessionApi
from cloud_client.models.auth_request_dto import AuthRequestDto
from cloud_client.api.recognize_api import RecognizeApi
from cloud_client.api.packages_api import PackagesApi
from cloud_client.models.audio_file_dto import AudioFileDto
from cloud_client.models.recognition_request_dto import RecognitionRequestDto

#whatson developer cloud speech processor
#from watson_developer_cloud import SpeechToTextV1


# Note: Is there a better way to do this?
# This is the file where the credentials are stored
import config

#speech_to_text = SpeechToTextV1(
#    iam_apikey=config.APIKEY,
#    url=config.URL
#)

from flask import Flask, render_template, request, jsonify, url_for, redirect, abort, session, json

PORT = 8080

# Global Variables
random_words = []
random_words_transliterated = []
random_string = ""
username = ""
user_directory = "Users/Test"
filename = ""
filename_wav = ""

app = Flask(__name__)


@app.route('/')
@app.route('/home')
def home():
    return render_template('main.html')


@app.route('/enroll', methods=["GET", "POST"])
def enroll():
    global username
    global user_directory

    if request.method == 'POST':
        data = request.get_json()

        username = data['username']
        password = data['password']
        repassword = data['repassword']

        user_directory = "Users/" + username + "/"

        # Create target directory & all intermediate directories if don't exists
        if not os.path.exists(user_directory):
            os.makedirs(user_directory)
            print("[ * ] Directory ", username,  " Created ...")
        else:
            print("[ * ] Directory ", username,  " already exists ...")
            print("[ * ] Overwriting existing directory ...")
            shutil.rmtree(user_directory, ignore_errors=False, onerror=None)
            os.makedirs(user_directory)
            print("[ * ] Directory ", username,  " Created ...")

        return redirect(url_for('voice'))

    else:
        return render_template('enroll.html')


@app.route('/auth', methods=['POST', 'GET'])
def auth():
    global username
    global user_directory
    global filename

    user_exist = False

    if request.method == 'POST':

        data = request.get_json()
        print(data)

        user_directory = 'Models/'
        username = data['username']
        password = data['password']

        print("[ DEBUG ] : What is the user directory at auth : ", user_directory)
        print("os.fsencode(user_directory : ", os.fsencode(user_directory))
        directory = os.fsencode(user_directory)
        print("directory : ", os.listdir(directory)[1:])

        for file in os.listdir(directory):
            print("file : ", file)
            filename = os.fsdecode(file)
            if filename.startswith(username):
                print("filename : ", filename)
                user_exist = True
                break
            else:
                pass

        if user_exist:
            print("[ * ] The user profile exists ...")
            return "User exist"

        else:
            print("[ * ] The user profile does not exists ...")
            return "Doesn't exist"

    else:
        print('its coming here')
        return render_template('auth.html')


@app.route('/vad', methods=['GET', 'POST'])
def vad():
    if request.method == 'POST':
        global random_words

        f = open('./static/audio/background_noise.wav', 'wb')
        f.write(request.data)
        f.close()

        background_noise = speech_recognition.AudioFile(
            './static/audio/background_noise.wav')
        with background_noise as source:
            speech_recognition.Recognizer().adjust_for_ambient_noise(source, duration=5)

        print("Voice activity detection complete ...")

        #random_words = RandomWords().random_words(count=5)
        random_words = russian_random_string()
        print(random_words)

        return "  ".join(random_words)

    else:
        background_noise = speech_recognition.AudioFile(
            './static/audio/background_noise.wav')
        with background_noise as source:
            speech_recognition.Recognizer().adjust_for_ambient_noise(source, duration=5)

        print("Voice activity detection complete ...")

        #random_words = RandomWords().random_words(count=5)
        random_words = russian_random_string()
        print(random_words)

        return "  ".join(random_words)


@app.route('/voice', methods=['GET', 'POST'])
def voice():
    global user_directory
    global filename_wav
    random_words_transliterated = []

    print("[ DEBUG ] : User directory at voice : ", user_directory)

    if request.method == 'POST':
        #    global random_string
        global random_words
        global username

        for word_str in random_words:
            random_words_transliterated.append(transliterate_str(word_str))


        filename_wav = user_directory + "-".join(random_words_transliterated) + '.wav'
        print(filename_wav)
        f = open(filename_wav, 'wb')
        f.write(request.data)
        f.close()

        with open(filename_wav, 'rb') as audio_file:
             #recognised_words = speech_to_text.recognize(audio_file, content_type='audio/wav').get_result()
             #print(recognised_words)

             session_api = SessionApi()
             credentials = AuthRequestDto(config.LOGIN, config.SERVER, config.PASSWORD)
             session_id = session_api.login(credentials).session_id
             print(session_id)

             packages_api = PackagesApi()
             packages_api.load(session_id, "CommonRus")

             recognize_api = RecognizeApi()
             data = audio_file.read()

             encoded_string = base64.standard_b64encode(data)
             string_str = str(encoded_string, 'ascii', 'ignore')

             audio_file_str = AudioFileDto(string_str, "audio/x-wav")
             recognition_request = RecognitionRequestDto(audio_file_str, "CommonRus")
             recognition_result = recognize_api.recognize(session_id, recognition_request)

             #print(recognition_result.text)

        recognised_words = recognition_result.text


        print("SpeechPro ASR thinks you said : " + recognised_words)
        print("SpeechPro Fuzzy partial score : " + str(fuzz.partial_ratio(random_words, recognised_words)))
        print("Speechpro Fuzzy score : " + str(fuzz.ratio(random_words, recognised_words)))

        if fuzz.ratio(random_words, recognised_words) < 50:
            print(
                "\nThe words you have spoken aren't entirely correct. Please try again ...")
            os.remove(filename_wav)
            return "fail"
        else:
            pass

        return "pass"

    else:
        return render_template('voice.html')


@app.route('/biometrics', methods=['GET', 'POST'])
def biometrics():
    global user_directory
    print("[ DEBUG ] : User directory is : ", user_directory)

    if request.method == 'POST':
        pass
    else:
        # MFCC
        print("Into the biometrics route.")

        directory = os.fsencode(user_directory)
        features = numpy.asarray(())

        for file in os.listdir(directory):
            filename_wav = os.fsdecode(file)
            if filename_wav.endswith(".wav"):
                print("[biometrics] : Reading audio files for processing ...")
                (rate, signal) = scipy.io.wavfile.read(user_directory + filename_wav)

                extracted_features = extract_features(rate, signal)

                if features.size == 0:
                    features = extracted_features
                else:
                    features = numpy.vstack((features, extracted_features))

            else:
                continue

        # GaussianMixture Model
        print("[ * ] Building Gaussian Mixture Model ...")

        gmm = GaussianMixture(n_components=16,
                            max_iter=200,
                            covariance_type='diag',
                            n_init=3)

        gmm.fit(features)
        print("[ * ] Modeling completed for user :" + username +
            " with data point = " + str(features.shape))

        # dumping the trained gaussian model
        # picklefile = path.split("-")[0]+".gmm"
        print("[ * ] Saving model object ...")
        pickle.dump(gmm, open("Models/" + str(username) +
                            ".gmm", "wb"), protocol=None)
        print("[ * ] Object has been successfully written to Models/" +
            username + ".gmm ...")
        print("\n\n[ * ] User has been successfully enrolled ...")

        features = numpy.asarray(())

        return "User has been successfully enrolled ...!!"


@app.route("/verify", methods=['GET'])
def verify():
    global username
    global filename
    global user_directory
    global filename_wav

    print("[ DEBUG ] : user directory : " , user_directory)
    print("[ DEBUG ] : filename : " , filename)
    print("[ DEBUG ] : filename_wav : " , filename_wav)

    # ------------------------------------------------------------------------------------------------------------------------------------#
    #                                                                   LTSD and MFCC                                                     #
    # ------------------------------------------------------------------------------------------------------------------------------------#

    # (rate, signal) = scipy.io.wavfile.read(audio.get_wav_data())
    (rate, signal) = scipy.io.wavfile.read(filename_wav)

    extracted_features = extract_features(rate, signal)

    # ------------------------------------------------------------------------------------------------------------------------------------#
    #                                                          Loading the Gaussian Models                                                #
    # ------------------------------------------------------------------------------------------------------------------------------------#

    gmm_models = [os.path.join(user_directory, user)
                  for user in os.listdir(user_directory)
                  if user.endswith('.gmm')]

    # print("GMM Models : " + str(gmm_models))

    # Load the Gaussian user Models
    models = [pickle.load(open(user, 'rb')) for user in gmm_models]

    user_list = [user.split("/")[-1].split(".gmm")[0]
                 for user in gmm_models]

    log_likelihood = numpy.zeros(len(models))

    for i in range(len(models)):
        gmm = models[i]  # checking with each model one by one
        scores = numpy.array(gmm.score(extracted_features))
        log_likelihood[i] = scores.sum()

    print("Log liklihood : " + str(log_likelihood))

    identified_user = numpy.argmax(log_likelihood)

    print("[ * ] Identified User : " + str(identified_user) +
          " - " + user_list[identified_user])

    auth_message = ""

    if user_list[identified_user] == username:
        print("[ * ] You have been authenticated!")
        auth_message = "success"
    else:
        print("[ * ] Sorry you have not been authenticated")
        auth_message = "fail"

    return auth_message


def calculate_delta(array):
    """Calculate and returns the delta of given feature vector matrix
    (https://appliedmachinelearning.blog/2017/11/14/spoken-speaker-identification-based-on-gaussian-mixture-models-python-implementation/)"""

    print("[Delta] : Calculating delta")

    rows, cols = array.shape
    deltas = numpy.zeros((rows, 20))
    N = 2
    for i in range(rows):
        index = []
        j = 1
        while j <= N:
            if i-j < 0:
                first = 0
            else:
                first = i-j
            if i+j > rows - 1:
                second = rows - 1
            else:
                second = i+j
            index.append((second, first))
            j += 1
        deltas[i] = (array[index[0][0]]-array[index[0][1]] +
                     (2 * (array[index[1][0]]-array[index[1][1]]))) / 10
    return deltas


def extract_features(rate, signal):
    print("[extract_features] : Exctracting featureses ...")

    mfcc_feat = mfcc(signal,
                     rate,
                     winlen=0.020,  # remove if not requred
                     preemph=0.95,
                     numcep=20,
                     nfft=1024,
                     ceplifter=15,
                     highfreq=6000,
                     nfilt=55,

                     appendEnergy=False)

    mfcc_feat = preprocessing.scale(mfcc_feat)

    delta_feat = calculate_delta(mfcc_feat)

    combined_features = numpy.hstack((mfcc_feat, delta_feat))

    return combined_features

def russian_random_string():
    filepath = './words.txt'
    with open(filepath) as fp:
       line = fp.readlines()
       split_line = line[randint(0,len(line))][0:-1].split(' ')
       return split_line

def transliterate_str(text_str):
    symbols = (u"абвгдеёжзийклмнопрстуфхцчшщъыьэюяАБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ", u"abvgdeejzijklmnoprstufhzcss_y_euaABVGDEEJZIJKLMNOPRSTUFHZCSS_Y_EUA")
    tr = {ord(a):ord(b) for a, b in zip(*symbols)}

    return text_str.translate(tr)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT, debug=True, ssl_context='adhoc')
