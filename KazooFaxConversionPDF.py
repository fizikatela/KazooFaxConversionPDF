#!/usr/bin/python
# -*- coding: utf-8 -*-
#__author__ = 'o.sidorov', 2015

import datetime
import os
import random
import urllib
import urlparse
import json
import requests
import cloudfiles
from subprocess import Popen, PIPE

def getNumberDomain(domainID, auth_token):
    base_url = 'http://'
    final_url = base_url + domainID
    head = {"Accept": "application/json", "Content-Type": "application/json", "X-Auth-Token": auth_token}
    req = requests.request("GET", url=final_url, headers=head)
    jsonTemp = json.loads(req.text)
    return jsonTemp['data']['caller_id']['external']['number']

def jsonGeneration(numberA, numberB, fileName, retries):
    urlBase = 'http://'
    urlEnd = urlBase + fileName
    json_dict = {"data": {"document": {"url": urlEnd, "method": "get"}, "retries": retries, "from_name": "FaxOut", "from_number": numberA, "to_name": "FaxOut", "to_number": numberB}}
    json_data = json.dumps(json_dict)
    json_post = json_data.encode('utf-8')
    return json_post

def putFax(id_domen, auth_token, text4json):
    base_url = 'http://'
    final_url = base_url + id_domen + '/faxes'
    head = {"Accept": "application/json", "Content-Type": "application/json", "X-Auth-Token": auth_token}
    req = requests.put(final_url, data = text4json, headers = head)
    return req.status_code

def fileNameGen(domainID):
    now_time = datetime.datetime.now()
    cur_hour = now_time.hour
    cur_minute = now_time.minute
    cur_second = now_time.second
    now_date = datetime.date.today()
    r = int(random.random() * 10 ** 10)
    return 'FAXOUT%s_%d_%s_%s-%s-%s' % (domainID, r, now_date, cur_hour, cur_minute, cur_second)

def file_w(date, fileName, fileType):
    local = '/tmp/fax_temp'
    fullAdrFile = '%s/%s.%s' % (local, fileName, fileType)
    if not (os.path.isdir(local)):
        os.makedirs(local)
    f = open(fullAdrFile, 'w')
    f.write(date)
    f.close()
    return fullAdrFile

def conversionToPDF(fullAdrFile, fileName):
    local = '/tmp/fax_temp'
    conAdrFile = '%s/%s.pdf' % (local, fileName)
    comm = 'convert -density 300 -quality 100 %s %s' % (fullAdrFile, conAdrFile)
    proc = Popen(comm, shell=True, stdout=PIPE, stderr=PIPE)
    proc.wait()
    return conAdrFile


def application(environ, start_response):
    username = ''
    api_key = ''
    api_key = urllib.unquote(api_key).decode('utf8')
    container_name = 'faxout'

    if (environ['REQUEST_METHOD'] == 'POST') or (environ['REQUEST_METHOD'] == 'PUT'):
        start_response('200 OK', [('Content-type', 'text/plain')])

        params = urlparse.parse_qs(environ['QUERY_STRING'])
        domenID = params.get('account_id', 'None')[0]
        authToken = params.get('auth_token', 'None')[0]
        numberA = getNumberDomain(domenID, authToken)
        numberB = params.get('number', 'None')[0]
        retries = params.get('retries', 'None')[0]
        fileName = fileNameGen(domenID)
        contentType = environ.get('CONTENT_TYPE')

        conn = cloudfiles.get_connection(username = username,
                                         api_key = api_key,
                                         authurl = 'https://')
        faxUser = conn.get_container(container_name)

        length = int(environ.get('CONTENT_LENGTH', 0))
        stream = environ['wsgi.input']
        tt = stream.read(length)

        if contentType == 'application/pdf':
            fileName = fileName + '.pdf'
            obj = faxUser.create_object(fileName)
            obj.content_type = contentType
            obj.write(tt)
        elif contentType == 'image/jpeg':
            fileType = 'jpg'
            fullAdrFile = file_w(tt, fileName, fileType)
            conAdrFile = conversionToPDF(fullAdrFile, fileName)
            fileName = fileName + '.pdf'
            obj = faxUser.create_object(fileName)
            obj.content_type = 'application/pdf'
            obj.load_from_filename(conAdrFile)
            os.remove(fullAdrFile)
            os.remove(conAdrFile)
        elif contentType == 'image/tiff':
            fileType = 'tiff'
            fullAdrFile = file_w(tt, fileName, fileType)
            conAdrFile = conversionToPDF(fullAdrFile, fileName)
            fileName = fileName + '.pdf'
            obj = faxUser.create_object(fileName)
            obj.content_type = 'application/pdf'
            obj.load_from_filename(conAdrFile)
            os.remove(fullAdrFile)
            os.remove(conAdrFile)
        else:
            return ['File type is not supported']

        text4json = jsonGeneration(numberA, numberB, fileName, retries)
        codePutFax = putFax(domenID, authToken, text4json)
        return ['A request to send a fax received']

    if environ['REQUEST_METHOD'] == 'GET':
        params = urlparse.parse_qs(environ['QUERY_STRING'])
        fileName = params.get('filename', 'None')[0]

        conn = cloudfiles.get_connection(username=username,
                                         api_key=api_key,
                                         authurl='http://')
        container = conn.get_container(container_name)

        if fileName.split('.')[-1] == 'pdf':
            headers = [('Content-Type', 'application/pdf')]
        elif fileName.split('.')[-1] == 'tiff':
            headers = [('Content-Type', 'image/tiff')]
        else:
            headers = [('Content-Type', 'text/plain')]
        start_response('200 OK', headers)

        try:
            tt = container.get_object(fileName)
            return environ['wsgi.file_wrapper'](tt.read(), 32768)

        except:
            start_response("404 no file", [("Content-Type", "text/html"), ("Content-Length", "0")])
            return ['404 no file']