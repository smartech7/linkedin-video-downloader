import os
import re
import sys
import requests
import click
from bs4 import BeautifulSoup as bs
from requests import Session
from llvd import config
from llvd.downloader import download_subtitles, download_video, download_exercises
from click_spinner import spinner
import re
from llvd.utils import clean_name


class App:
    def __init__(self, email, password, course_slug, resolution, caption, throttle):

        self.email = email
        self.password = password
        self.course_slug = course_slug
        self.link = ""
        self.video_format = resolution
        self.caption = caption
        self.headers = {}
        self.cookies = {}
        self.chapter_path = ""
        self.current_video_index = None
        self.current_video_name = ""
        self.throttle = throttle

    def login(self, s, login_data):
        """
            Login the user
        """
        with spinner():

            s.post(
                config.signup_url, login_data)
            cookies = s.cookies.get_dict()
            self.cookies["JSESSIONID"] = cookies.get("JSESSIONID").replace(
                '\"', "")
            self.cookies["li_at"] = cookies.get("li_at")
            self.headers["Csrf-Token"] = cookies.get("JSESSIONID").replace(
                '\"', "")

            if cookies.get("li_at") == None:
                return None
            return 200

    def run(self, cookies=None):
        """
        Main function, tries to login the user and when it succeeds, tries to download the course
        """
        try:

            if cookies is not None:
                self.cookies["JSESSIONID"] = cookies.get("JSESSIONID")
                self.cookies["li_at"] = cookies.get("li_at")
                self.headers["Csrf-Token"] = cookies.get("JSESSIONID")
                self.download_entire_course()
            else:
                with Session() as s:
                    site = s.get(config.login_url)
                    bs_content = bs(site.content, "html.parser")

                    csrf = bs_content.find(
                        'input', {'name': 'csrfToken'}).get("value")
                    loginCsrfParam = bs_content.find(
                        "input", {"name": "loginCsrfParam"}).get("value")
                    login_data = {"session_key": self.email, "session_password": self.password,
                                  "csrfToken": csrf, "loginCsrfParam": loginCsrfParam}

                    status = self.login(s, login_data)

                    if status is None:
                        click.echo(
                            click.style(f"Wrong credentials, try again", fg="red"))
                        sys.exit(0)
                    else:
                        if not os.path.exists(f'{self.course_slug}'):
                            os.makedirs(f'{self.course_slug}')
                        self.download_entire_course()

        except ConnectionError:
            click.echo(click.style(f"Failed to connect", fg="red"))

    @staticmethod
    def resume_failed_ownloads():
        """
            Resume failed downloads
        """
        current_files = [file for file in os.listdir() if ".mp4" in file]
        if len(current_files) > 0:
            for file in current_files:
                if os.stat(file).st_size == 0:
                    os.remove(file)
            click.echo(click.style(f"Resuming download..", fg="red"))

    def download_entire_course(self):
        """
            Download a course
        """
        self.resume_failed_ownloads()
        try:
            r = requests.get(config.course_url.format(
                self.course_slug), cookies=self.cookies, headers=self.headers)
            course_name = r.json()['elements'][0]['title']
            course_name = re.sub(r'[\\/*?:"<>|]', "", course_name)
            chapters = r.json()['elements'][0]['chapters']
            exercise_files = r.json()["elements"][0]["exerciseFileUrls"]
            chapters_index = 1
            delay = self.throttle

            for chapter in chapters:
                chapter_name = chapter["title"]
                videos = chapter["videos"]
                chapter_path = f'./{self.course_slug}/{chapters_index:0=2d}-{clean_name(chapter_name)}'
                course_path = f'./{self.course_slug}'
                chapters_index += 1
                video_index = 1
                self.chapter_path = f'./{self.course_slug}/{chapters_index-1:0=2d}-{clean_name(chapter_name)}'
                if not os.path.exists(chapter_path):
                    os.makedirs(chapter_path)
                for video in videos:
                    video_name = re.sub(r'[\\/*?:"<>|]', "",
                                        video['title'])
                    self.current_video_name = video_name
                    video_slug = video['slug']
                    video_url = config.video_url.format(
                        self.course_slug, self.video_format, video_slug)
                    page_data = requests.get(
                        video_url, cookies=self.cookies, headers=self.headers)
                    page_json = page_data.json()
                    self.current_video_index = video_index

                    try:
                        download_url = page_json['elements'][0]['selectedVideo']['url']['progressiveUrl']
                        try:
                            subtitles = page_json['elements'][0]['selectedVideo']['transcript']
                        except:
                            click.echo(click.style(
                                f"Subtitles not found", fg="red"))
                            subtitles = None
                        duration_in_ms = int(page_json['elements'][0]
                                             ['selectedVideo']['durationInSeconds']) * 1000

                        click.echo(
                            click.style(f"\nCurrent: {chapters_index-1:0=2d}-{clean_name(chapter_name)}/"\
                                f"{video_index:0=2d}-{video_name}.mp4 @{self.video_format}p"))
                        current_files = []
                        for file in os.listdir(chapter_path):
                            if file.endswith(".mp4") and "-" in file:
                                ff = re.split(
                                    "\d+-", file)[1].replace(".mp4", "")
                                current_files.append(ff)
                    except Exception as e:
                        if 'url' in str(e):
                            click.echo(
                                click.style(f"This video is locked, you probably "\
                                    f"need a premium account", fg="red"))
                        else:
                            click.echo(
                                click.style(f"Failed to download {video_name}", fg="red"))
                    else:
                        if clean_name(video_name) not in current_files:
                            download_video(download_url, video_index, video_name, chapter_path, delay)
                            if subtitles is not None and self.caption:
                                subtitle_lines = subtitles['lines']
                                download_subtitles(
                                    video_index, subtitle_lines, video_name, chapter_path, duration_in_ms)
                        else:
                            click.echo(f"Skipping already existing video...")
                            
                    video_index += 1

            if len(exercise_files) > 0:
                download_exercises(exercise_files, course_path)
            click.echo("\nFinished, start learning! :)")
        except requests.exceptions.TooManyRedirects:
                    click.echo(click.style(f"Your cookie is expired", fg="red"))
        except KeyError:
                click.echo(click.style(f"That course is not found", fg="red"))
        except Exception as e:
            os.remove(f'{self.chapter_path}/{self.current_video_index:0=2d}-{clean_name(self.current_video_name)}.mp4')
            self.download_entire_course()
            
