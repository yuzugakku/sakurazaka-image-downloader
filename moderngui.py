import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re

# import sys
from datetime import datetime
from threading import Thread

# import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk

# --- Utility Functions ---


def reverse_and_pascal_case(text):
    """
    Converts a string (e.g., 'RIKA ISHIMORI') to a reversed PascalCase (e.g., 'IshimoriRika').
    """
    if not text:
        return ""

    parts = re.split(r"[\s\-_]+", text.lower())
    parts.reverse()
    return "".join(word.capitalize() for word in parts)


def sanitize_name(name, is_folder=False):
    """Remove illegal characters and query strings from a filename or folder name."""
    name = name.split("?")[0]
    if is_folder:
        # For folders: remove non-alphanumeric characters
        name = re.sub(r"[^\w]", "", name).strip()
    else:
        # For files: replace non-alphanumeric/hyphen/dot with underscore
        name = re.sub(r"[^\w\-\.]", "_", name)
    return name


# --- Core Download Function ---


class Downloader:
    def __init__(self, app_instance):
        self.app = app_instance
        self._stop_event = False

    def stop(self):
        """Sets the internal flag to stop the download loop."""
        self._stop_event = True

    def start_process(self, url, status_callback, path_callback):
        """Handles the main scraping and downloading logic."""
        self._stop_event = False  # Reset stop flag
        main_image_folder = Path("images")

        try:
            base_url = "https://" + urlparse(url).netloc
        except Exception:
            status_callback("Error: Invalid URL structure.")
            return

        status_callback("Fetching URL...")

        try:
            # 1. Fetch HTML
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            html_content = response.text
            soup = BeautifulSoup(html_content, "html.parser")

            # 2. Get Member Name and Define Base Folder
            p_tag = soup.find("p", class_="eigo wf-a")
            if not p_tag:
                status_callback(
                    'Error: English name tag (<p class="eigo wf-a">) not found.'
                )
                return

            member_name_raw = p_tag.get_text(strip=True)
            reversed_pascal_case_name = reverse_and_pascal_case(member_name_raw)
            member_subfolder_name = sanitize_name(
                reversed_pascal_case_name, is_folder=True
            )

            if not member_subfolder_name:
                status_callback("Error: Sanitized member name is empty.")
                return

            # 3. Get Date Folder Name (YYMMDD)
            date_folder_name = datetime.now().strftime("%y%m%d")

            # Define the final target directory: images/IshimoriRika/251018
            target_folder = main_image_folder / member_subfolder_name / date_folder_name

            # 4. Create the full nested directory structure
            target_folder.mkdir(parents=True, exist_ok=True)
            path_callback(f"Saving to: {target_folder.as_posix()}")
            status_callback(f"Target folder created: {date_folder_name}")

            # 5. Find images
            article_box = soup.find("div", class_="box-article")

            if article_box:
                status_callback("Searching for images...")
                image_tags = article_box.find_all("img")
                status_callback(f"Found {len(image_tags)} image tags.")
                downloaded_count = 0

                # --- Download Images ---
                for i, img in enumerate(image_tags):
                    if self._stop_event:
                        status_callback("Download stopped by user.")
                        break

                    relative_url = img.get("src") or img.get("data-src")

                    if relative_url:
                        full_image_url = urljoin(base_url, relative_url)

                        url_path = urlparse(full_image_url).path
                        original_filename = Path(url_path).name
                        sanitized_name = sanitize_name(original_filename)

                        filename = target_folder / f"{i+1:02d}_{sanitized_name}"

                        if not filename.suffix:
                            filename = filename.with_suffix(".jpg")

                        try:
                            img_response = requests.get(
                                full_image_url, stream=True, timeout=15
                            )
                            img_response.raise_for_status()

                            with filename.open("wb") as f:
                                for chunk in img_response.iter_content(chunk_size=8192):
                                    f.write(chunk)

                            status_callback(f"  Downloaded: {filename.name}")
                            downloaded_count += 1

                        except requests.exceptions.RequestException as img_e:
                            status_callback(
                                f"  Error downloading {full_image_url}: {img_e}"
                            )
                        except Exception as save_e:
                            status_callback(
                                f"  Error saving file {filename.name}: {save_e}"
                            )
                    else:
                        status_callback(
                            f"  Image tag {i+1} has no valid source attribute."
                        )

            else:
                status_callback(
                    "Element with the specified class 'box-article' not found."
                )

        except requests.exceptions.RequestException as e:
            status_callback(f"An error occurred during initial request: {e}")
        except Exception as e:
            status_callback(f"An unexpected error occurred: {e}")

        status_callback("---")
        if self._stop_event:
            status_callback("Download process aborted. 🛑")
        else:
            status_callback(
                f"Image download complete! Downloaded {downloaded_count} files. ✅"
            )

        # Always re-enable the button after process ends
        self.app.download_button.configure(state=ctk.NORMAL, text="Start Download")
        self.app.stop_button.configure(state=ctk.DISABLED)


# --- GUI Implementation ---


class ImageDownloaderApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("🌸 Sakurazaka46 Image Downloader")
        self.geometry("600x650")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # Log area takes available space

        self.downloader = Downloader(self)
        self.thread = None

        # Set appearance and color theme
        ctk.set_appearance_mode("System")  # Options: "System", "Dark", "Light"
        ctk.set_default_color_theme("green")  # Options: "blue", "green", "dark-blue"

        # Default URL
        default_url = (
            "https://sakurazaka46.com/s/s46/diary/detail/66196?ima=0000&cd=blog"
        )

        # 1. URL Input Frame
        url_frame = ctk.CTkFrame(self)
        url_frame.grid(row=0, column=0, padx=20, pady=(20, 10), sticky="ew")
        url_frame.columnconfigure(1, weight=1)

        ctk.CTkLabel(url_frame, text="Blog URL:").grid(
            row=0, column=0, padx=(10, 5), pady=10, sticky="w"
        )

        self.url_entry = ctk.CTkEntry(url_frame, width=450)
        self.url_entry.insert(0, default_url)
        self.url_entry.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="ew")

        # 2. Control Buttons Frame
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
        button_frame.columnconfigure((0, 1), weight=1)

        self.download_button = ctk.CTkButton(
            button_frame, text="Start Download 🚀", command=self.run_download_in_thread
        )
        self.download_button.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

        self.stop_button = ctk.CTkButton(
            button_frame,
            text="Stop Download 🛑",
            command=self.stop_download,
            fg_color="red",
            state=ctk.DISABLED,
        )
        self.stop_button.grid(row=0, column=1, padx=10, pady=10, sticky="ew")

        # 3. Path and Clear Log Frame
        path_frame = ctk.CTkFrame(self)
        path_frame.grid(row=2, column=0, padx=20, pady=(0, 10), sticky="ew")
        path_frame.columnconfigure(0, weight=1)

        ctk.CTkLabel(path_frame, text="Current Save Path:").grid(
            row=0, column=0, padx=10, pady=(5, 0), sticky="w"
        )
        self.path_display = ctk.CTkLabel(path_frame, text="N/A", text_color="yellow")
        self.path_display.grid(row=1, column=0, padx=10, sticky="w")

        self.clear_log_button = ctk.CTkButton(
            path_frame, text="Clear Log", command=self.clear_log, width=80
        )
        self.clear_log_button.grid(row=1, column=1, padx=10, pady=5, sticky="e")

        # 4. Status Log Text Area
        log_frame = ctk.CTkFrame(self)
        log_frame.grid(row=3, column=0, padx=20, pady=(0, 20), sticky="nsew")
        log_frame.grid_columnconfigure(0, weight=1)
        log_frame.grid_rowconfigure(0, weight=1)

        self.log_text = ctk.CTkTextbox(log_frame, height=200)
        self.log_text.insert("end", "Welcome! Enter a URL and click Start Download.")
        self.log_text.configure(state="disabled")
        self.log_text.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def update_status(self, message):
        """Adds a message to the log text area."""
        self.log_text.configure(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")  # Auto-scroll to the bottom
        self.log_text.configure(state="disabled")
        self.update_idletasks()  # Ensure the GUI updates immediately

    def update_path_display(self, message):
        """Updates the dedicated path display label."""
        self.path_display.configure(text=message, text_color="lightblue")

    def clear_log(self):
        """Clears the status log."""
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")

    def run_download_in_thread(self):
        """Starts the download function in a separate thread."""
        url = self.url_entry.get().strip()

        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        self.clear_log()
        self.path_display.configure(text="N/A", text_color="yellow")

        self.download_button.configure(state=ctk.DISABLED, text="Working...")
        self.stop_button.configure(state=ctk.NORMAL)

        # Start the download function in a thread
        self.thread = Thread(
            target=self.downloader.start_process,
            args=(url, self.update_status, self.update_path_display),
        )
        self.thread.start()

    def stop_download(self):
        """Requests the background downloader to stop."""
        self.downloader.stop()
        self.stop_button.configure(state=ctk.DISABLED, text="Stopping...")
        self.update_status("Stopping download gracefully...")


# --- Run the GUI ---
if __name__ == "__main__":
    app = ImageDownloaderApp()
    app.mainloop()
