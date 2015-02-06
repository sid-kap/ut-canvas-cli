#!/usr/bin/python3
import requests
import pyCookieCheat
import json
from bs4 import BeautifulSoup
from colors import red, green, blue, color
from blessings import Terminal
import arrow
from textwrap import fill
from nameparser import HumanName

import dateutil.parser
import os
import sys

import click

session = requests.Session()

@click.group()
def cli():
    pass

def get_json(url):
    cookies = pyCookieCheat.chrome_cookies(url)
    r = session.get(url, cookies = cookies)
    text = r.text

    if text.startswith('while(1);'):
        text = r.text[9:]
    return json.loads(text)

def download_file(url, local_filename):
    # local_filename = url.split('/')[-1]

    # NOTE the stream=True parameter
    print(url)
    r = session.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                f.flush()
    return local_filename

def capitalize_name(name):
    human_name = HumanName(name)
    human_name.capitalize()
    return str(human_name)
 
class Message:
    def __init__(self, **kwargs):
        self.body = kwargs['body']
        self.created_at = kwargs['created_at']
        self.author_id = kwargs['author_id']
        self.author_name = capitalize_name(kwargs['author_name'])
    
    def __str__(self, include_author=True):
        string = ''
        if include_author:
            string += color(self.author_name, fg=4) + '\n' 
        string += self.body
        return string

class Thread:
    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.subject = kwargs['subject']
        self.messages = None
        self.unread = (kwargs['workflow_state'] == 'read')
        self.message_count = kwargs['message_count']


    def load_messages(self):
        if self.messages is None:
            url = 'https://utexas.instructure.com/api/v1/conversations/{0}?include_participant_contexts=false&include_private_conversation_enrollments=false'.format(self.id)
            thread = get_json(url) 

            self.messages = []

            for message in thread['messages']:
                author_id = message['author_id']
                author_name = None
                
                for participant in thread['participants']:
                    if participant['id'] == author_id:
                        author_name = participant['name']
                        break

                message['author_name'] = author_name
                
                self.messages.append(Message(**message))

    def __str__(self):
        if self.messages is None:
            self.load_messages()
        subject = color(self.subject, fg=2, style='bold')

        include_author = (self.message_count != 1)
        messages = '\n'.join([m.__str__(include_author=include_author) for m in self.messages])

        title_line = None

        if self.message_count == 1:
            title_line = color(self.messages[0].author_name, fg=4) + ' ' + subject
        else:
            title_line = subject       
        return '~~~\n' + title_line + '\n' + messages


courses = [(1127265, 'FRI'),
           (1135180, 'Waves')]

@cli.command()
def messages():
    url = 'https://utexas.instructure.com/api/v1/conversations?scope=inbox&filter_mode=and&include_private_conversation_enrollments=false'
    j = get_json(url)

#    threads = [] 

    for obj in j:
#        print(json.dumps(obj, indent=4))
        thread = Thread(**obj)
#        threads.append(thread)
        print(thread)

class File:
    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.filename = kwargs['filename']
        self.url = kwargs['url']
        self.updated_at = kwargs['updated_at']
        self.locked_for_user = kwargs['locked_for_user']

    def download(self, dir):
        if self.locked_for_user:
            return
        filename = dir + '/' + self.filename

        updated_at = int(dateutil.parser.parse(self.updated_at).strftime('%s'))
        download = not(os.path.isfile(filename) and os.path.getmtime(filename) > updated_at)
        if download:
            download_file(self.url, filename) 

class Folder:
    def __init__(self, **kwargs):
        self.id = kwargs['id']
        self.name = kwargs['name']
        self.files = []
        self.folders = []

        if kwargs['files_count']:
            files = get_json('https://utexas.instructure.com/api/v1/folders/{0}/files'.format(self.id))
            for file in files:
                self.files.append(File(**file))

        if kwargs['folders_count']:
            folders = get_json('https://utexas.instructure.com/api/v1/folders/{0}/folders'.format(self.id))
            for folder in folders:
                self.folders.append(Folder(**folder))

    def download(self, dir):
        new_dir = dir + '/' + self.name
        #print(new_dir)
        if not os.path.exists(new_dir):
            os.makedirs(new_dir)
        for folder in self.folders:
            folder.download(new_dir)
        for file in self.files:
            file.download(new_dir)

@cli.command()
# @click.argument('course_id')
def files():
    courses = get_json('https://utexas.instructure.com/api/v1/courses/')
    
    if 'errors' in courses and len(courses['errors']):
        print('You are not signed in.', file=sys.stderr)
        return

    for course in courses:
        # only get courses from Spring 2015
        if course['enrollment_term_id'] == 4377:
            course_id = course['id']
            course_name = course['name'].title()

            course_folder = get_json('https://utexas.instructure.com/api/v1/courses/{0}/folders/root'.format(course_id))
            folder_id = course_folder['id']
            root_folder_obj = get_json('https://utexas.instructure.com/api/v1/folders/{0}/'.format(folder_id))
            root_folder = Folder(**root_folder_obj)
            root_folder.download('/home/sidharth/workspace/canvas_files/{0}'.format(course_name))

@cli.command()
def announcements():
    t = Terminal()
    w = t.width

    for id, course in courses:
        print(color(course, fg=3, style='bold'))

        url = 'https://utexas.instructure.com/api/v1/courses/{0}/discussion_topics?only_announcements=true'.format(id)
        j = get_json(url)

        for obj in j:
            # print(json.dumps(obj, indent=4))
            title  = obj['title']
            author = capitalize_name(obj['author']['display_name'])
            time   = arrow.get(obj['posted_at']).humanize()

            print( color(title.center(w),  fg=2, style='bold') )
            print( color(author.center(w), fg=1) )
            print( color(time.center(w),   fg=1) )
            
            soup = BeautifulSoup(obj['message'])
            # print(soup.text)
            print(fill(soup.text, w, replace_whitespace=False))
            print()
    

if __name__=='__main__':
    cli()
