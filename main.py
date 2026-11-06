import os
import re
import time
import threading
import csv
import logging
import requests
from kivymd.uix.list import OneLineListItem
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.clock import mainthread
from kivy.core.audio import SoundLoader
from kivy.utils import platform

from kivymd.app import MDApp
from kivymd.uix.screenmanager import MDScreenManager
from kivymd.uix.screen import MDScreen
from kivymd.uix.dialog import MDDialog
from kivymd.uix.button import MDFlatButton


from kivy.utils import platform

def get_video_id(url_or_id):
    url_or_id = url_or_id.strip()
    if url_or_id.isdigit():
        return url_or_id
        
    if "vm.tiktok.com" in url_or_id or "vt.tiktok.com" in url_or_id or "/t/" in url_or_id:
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            # Added timeout and raise_for_status to catch bad responses
            response = requests.get(url_or_id, headers=headers, allow_redirects=True, timeout=15)
            response.raise_for_status() 
            url_or_id = response.url
        except requests.exceptions.Timeout:
            raise Exception("Connection timed out while resolving the TikTok link. Check your internet.")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error resolving link: {str(e)}")
        except Exception as e:
            raise Exception(f"Unexpected error resolving link: {str(e)}")
            
    try:
        match = re.search(r'/video/(\d+)', url_or_id)
        if match:
            return match.group(1)
    except Exception as e:
        raise Exception(f"Error parsing the URL: {str(e)}")
        
    return None

class AppScreenManager(MDScreenManager):
    pass






def export_to_public_downloads(private_file_path, public_filename):
    if platform != 'android':
        return False

    if not os.path.isfile(private_file_path):
        raise FileNotFoundError(f"CSV file does not exist: {private_file_path}")
    if not public_filename or os.path.basename(public_filename) != public_filename:
        raise ValueError("The export filename must be a non-empty filename, not a path.")

    from jnius import autoclass, cast

    BuildVersion = autoclass('android.os.Build$VERSION')
    if BuildVersion.SDK_INT < 29:
        raise RuntimeError(
            "Public Downloads export requires Android 10 (API 29) or later. "
            "The CSV is still saved in the app's private storage."
        )

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    ContentValues = autoclass('android.content.ContentValues')
    MediaStore = autoclass('android.provider.MediaStore$Downloads')
    Environment = autoclass('android.os.Environment')

    activity = PythonActivity.mActivity
    if activity is None:
        raise RuntimeError("The Android activity is not available; try exporting again.")

    context = cast('android.content.Context', activity)
    resolver = context.getContentResolver()
    values = ContentValues()
    values.put("_display_name", public_filename)
    values.put("mime_type", "text/csv")
    values.put("relative_path", Environment.DIRECTORY_DOWNLOADS + "/")
    values.put("is_pending", 1)

    uri = resolver.insert(MediaStore.EXTERNAL_CONTENT_URI, values)
    if uri is None:
        raise OSError("Android could not create the file in the public Downloads folder.")

    output_stream = None
    try:
        output_stream = resolver.openOutputStream(uri, "w")
        if output_stream is None:
            raise OSError("Android could not open the exported file for writing.")

        with open(private_file_path, "rb") as input_file:
            while True:
                chunk = input_file.read(64 * 1024)
                if not chunk:
                    break
                output_stream.write(chunk, 0, len(chunk))

        output_stream.close()
        output_stream = None

        published_values = ContentValues()
        published_values.put("is_pending", 0)
        if resolver.update(uri, published_values, None, None) != 1:
            raise OSError("Android could not finish publishing the exported CSV.")
    except Exception:
        if output_stream is not None:
            try:
                output_stream.close()
            except Exception:
                logging.exception("Could not close the incomplete Downloads export stream.")
        try:
            resolver.delete(uri, None, None)
        except Exception:
            logging.exception("Could not remove the incomplete Downloads export.")
        raise

    return True





class TikTokScraperApp(MDApp):
    dialog = None

    def build(self):
        self.theme_cls.primary_palette = "Red"
        self.theme_cls.theme_style = "Light" 
        self.click_sound = SoundLoader.load('click.wav')
        self.stop_download = False
        
        # BIND THE BACK BUTTON
        Window.bind(on_keyboard=self.hook_keyboard)
        
        # REQUEST ANDROID STORAGE PERMISSIONS AT RUNTIME
        if platform == 'android':
            from android.permissions import request_permissions, Permission
            request_permissions([
                Permission.READ_EXTERNAL_STORAGE, 
                Permission.WRITE_EXTERNAL_STORAGE
            ])
        
        return Builder.load_file('main.kv')

    def hook_keyboard(self, window, key, *args):
        if key == 27:
            if self.dialog and getattr(self.dialog, 'parent', None): 
                self.dismiss_error()
                return True
            
            if self.root.current == "downloading":
                # Safely stop the thread if it is running, otherwise go home
                if not self.stop_download:
                    self.cancel_download()
                else:
                    self.reset_to_home()
                return True
                
            if self.root.current == "home":
                return False 

            return True


    def handle_cancel_button(self):
            # If the button says "GO BACK", go home. Otherwise, cancel.
            if self.root.ids.cancel_btn.text == "GO BACK":
                self.reset_to_home()
            else:
                self.cancel_download()

    
    def dismiss_error(self, *args):
        """Helper to dismiss errors and force navigation to Home"""
        self.play_click_sound()
        if self.dialog:
            self.dialog.dismiss()
        self.root.current = "home"

    def show_error(self, text):
        """Screen 2: Error Popup (Updated to use dismiss_error)"""
        self.play_click_sound()
        if not self.dialog:
            self.dialog = MDDialog(
                text=text,
                buttons=[
                    MDFlatButton(
                        text="BACK",
                        theme_text_color="Custom",
                        text_color=self.theme_cls.primary_color,
                        on_release=self.dismiss_error # Forces user back to home screen
                    )
                ],
            )
        else:
            self.dialog.text = text
        self.dialog.open()

    # ... (Keep the rest of your methods like start_download, run_scraper_thread exactly as they were) ...

    def play_click_sound(self):
        if self.click_sound:
            self.click_sound.play()


    def githeri(self):
        self.play_click_sound()

    def start_download(self):
        try:
            self.play_click_sound()
            url = self.root.ids.url_input.text.strip()
            
            if not url:
                self.show_error("Please enter a URL or Video ID.")
                return

            self.root.current = "downloading"
            self.root.ids.status_label.text = "Resolving link..."
            self.root.ids.status_label.text_color = "black"
            self.stop_download = False
            
            threading.Thread(target=self.run_scraper_thread, args=(url,), daemon=True).start()
        except Exception as e:
            # If thread fails to start or UI crashes, show popup and reset
            self.show_error(f"Failed to start process: {str(e)}")
            self.reset_to_home()

    def cancel_download(self):
        self.play_click_sound()
        self.stop_download = True
        self.root.ids.status_label.text = "Cancelling safely..."

    @mainthread
    def update_ui_status(self, text, color="black", done=False):
        self.root.ids.status_label.text = text
        if color == "green":
            self.root.ids.status_label.text_color = (0, 0.7, 0, 1)
        else:
            self.root.ids.status_label.text_color = self.theme_cls.text_color

        if done:
            self.root.ids.spinner.active = False
            self.root.ids.cancel_btn.text = "GO BACK"
            self.root.ids.cancel_btn.on_release = self.reset_to_home
            self.refresh_file_list()

    def reset_to_home(self):
        self.play_click_sound()
        self.root.current = "home"
        self.root.ids.spinner.active = True
        self.root.ids.cancel_btn.text = "CANCEL"
        self.root.ids.cancel_btn.on_release = self.cancel_download
        self.root.ids.url_input.text = ""

    def run_scraper_thread(self, url):
        # 1. Safely attempt to resolve the ID
        try:
            self.update_ui_status("Checking link...")
            video_id = get_video_id(url)
            
            if not video_id:
                self.update_ui_status("Error: Could not find a valid Video ID in the link.", done=True)
                return
                
            self.update_ui_status(f"Starting scrape for ID:\n{video_id}")
            
        except Exception as e:
            # Catches timeouts and network errors from get_video_id
            self.update_ui_status(f"Error: {str(e)}", done=True)
            return

        # 2. Continue with the rest of your original setup...
        if platform == 'android':
            from android.storage import primary_external_storage_path
            writable_folder = MDApp.get_running_app().user_data_dir
        else:
            writable_folder = os.path.expanduser("~")
            
        # ... (Keep the rest of your original try/except block for the scraping loop)
            
        # Ensure timestamp is used to avoid Scoped Storage overwrite conflicts
        filename = f"tiktok_{video_id}_{int(time.time())}_full.csv"
        save_path = os.path.join(writable_folder, filename)
        
        all_comments = []
        cursor = 0
        has_more = 1
        
        headers = {"User-Agent": "Mozilla/5.0 (Android 10; Mobile; rv:109.0)"}
        
        try:
            while has_more and not self.stop_download:
                url = f"https://www.tiktok.com/api/comment/list/?aid=1988&aweme_id={video_id}&count=30&cursor={cursor}"
                self.update_ui_status(f"Fetching batch at cursor {cursor}...")
                
                response = requests.get(url, headers=headers, timeout=10)
                data = response.json()
                current_batch = data.get('comments', [])
                
                if not current_batch:
                    break

                for c in current_batch:
                    if self.stop_download:
                        break
                    
                    reply_count = c.get('reply_comment_total', 0)
                    all_comments.append({
                        "Type": "Comment",
                        "User": c['user']['unique_id'],
                        "Text": c['text'].replace('\n', ' '), # Clean newlines for CSV safety
                        "Reply_Count": reply_count
                    })

                has_more = data.get('has_more', 0)
                cursor = data.get('cursor', 0)
                time.sleep(1)

        except Exception as e:
            self.update_ui_status(f"Error occurred: {str(e)}", done=True)
            return

        if all_comments:
            self.update_ui_status("Saving to CSV...")
            try:
                # Built-in CSV writing (zero external dependencies)
                with open(save_path, mode='w', newline='', encoding='utf-8-sig') as f:
                    writer = csv.DictWriter(f, fieldnames=["Type", "User", "Text", "Reply_Count"])
                    writer.writeheader()
                    writer.writerows(all_comments)
            except Exception as e:
                self.update_ui_status(f"Save failed: {str(e)}", done=True)
                return

            if platform == 'android':
                try:
                    export_to_public_downloads(save_path, filename)
                except Exception as e:
                    self.update_ui_status(
                        f"CSV saved in app storage:\n{save_path}\n\n"
                        f"Could not export it to public Downloads: {e}",
                        done=True
                    )
                    return
                self.update_ui_status(
                    f"DONE!\nSaved in app storage:\n{save_path}\n"
                    f"Also exported to public Downloads as:\n{filename}",
                    color="green",
                    done=True
                )
            else:
                self.update_ui_status(
                    f"DONE!\nSaved to:\n{save_path}",
                    color="green",
                    done=True
                )
        else:
            self.update_ui_status("Stopped. No data collected.", done=True)

    # ... (rest of your run_scraper_thread method is up here) ...

    def on_start(self):
        # Automatically load files when the app opens
        self.refresh_file_list()

    def refresh_file_list(self):
        try:
            file_list_widget = self.root.ids.file_list
            file_list_widget.clear_widgets() # Removes the static placeholder text
            
            if platform == 'android':
                directory = MDApp.get_running_app().user_data_dir
            else:
                directory = os.path.expanduser("~")
                
            files_found = False
            if os.path.exists(directory):
                # Get all CSVs and sort them by newest first
                files = [f for f in os.listdir(directory) if f.endswith('.csv')]
                files.sort(key=lambda x: os.path.getmtime(os.path.join(directory, x)), reverse=True)
                
                for filename in files:
                    filepath = os.path.join(directory, filename)
                    
                    # Create a clickable item for each file
                    item = OneLineListItem(
                        text=filename,
                        on_release=lambda x, p=filepath: self.open_file(p)
                    )
                    file_list_widget.add_widget(item)
                    files_found = True
                    
            if not files_found:
                from kivymd.uix.label import MDLabel
                file_list_widget.add_widget(MDLabel(
                    text="No downloaded files found.", 
                    halign="center", 
                    padding_y="30dp"
                ))
                
        except Exception as e:
            # Failsafe: Shows an error popup instead of crashing the app
            self.show_error(f"Could not load file list: {str(e)}")

    def open_file(self, filepath):
        self.play_click_sound()
        try:
            if platform == 'android':
                # Safest approach for Android to prevent FileProvider security crashes
                filename = os.path.basename(filepath)
                self.show_error(f"'{filename}' is exported to your public Downloads folder.\n\nOpen your phone's File Manager or a suitable app to view it.")
            else:
                # Natively opens the file in Excel/Notepad on Desktop
                import subprocess, sys
                if os.name == 'nt':
                    os.startfile(filepath)
                elif sys.platform == 'darwin':
                    subprocess.call(('open', filepath))
                else:
                    subprocess.call(('xdg-open', filepath))
        except Exception as e:
            self.show_error(f"Cannot open file: {str(e)}")


if __name__ == "__main__":
    TikTokScraperApp().run()


