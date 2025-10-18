import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re
import tkinter as tk
from tkinter import messagebox
from threading import Thread  # Use threads to prevent the GUI from freezing

# --- Utility Functions ---


def reverse_and_pascal_case(text):
    """
    Converts a string (e.g., 'RIKA ISHIMORI') to a reversed PascalCase (e.g., 'IshimoriRika').
    """
    if not text:
        return ""

    # 1. Split the name into parts (words)
    parts = re.split(r"[\s\-_]+", text.lower())

    # 2. Reverse the order of the parts (e.g., ['rika', 'ishimori'] -> ['ishimori', 'rika'])
    parts.reverse()

    # 3. Capitalize each part and join them without spaces (PascalCase)
    return "".join(word.capitalize() for word in parts)


def sanitize_name(name, is_folder=False):
    """Remove illegal characters and query strings from a filename or folder name."""
    # Remove query parameters
    name = name.split("?")[0]
    # For folders, replace non-word characters with nothing, leaving a clean name.
    if is_folder:
        name = re.sub(r"[^\w]", "", name).strip()
    # For files, replace non-word characters with an underscore.
    else:
        name = re.sub(r"[^\w\-\.]", "_", name)
    return name


# --- Core Download Function ---


def start_download_process(url, status_callback):
    """Handles the main scraping and downloading logic."""
    main_image_folder = Path("images")
    base_url = "https://" + urlparse(url).netloc

    status_callback("Fetching URL...")

    try:
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        html_content = response.text
        soup = BeautifulSoup(html_content, "html.parser")

        # 1. Get the subfolder name from <p class="eigo wf-a">
        p_tag = soup.find("p", class_="eigo wf-a")
        if not p_tag:
            status_callback(
                'Error: English name tag (<p class="eigo wf-a">) not found.'
            )
            return

        member_name_raw = p_tag.get_text(strip=True)

        # Reverse the name order and convert to PascalCase (e.g., Rika Ishimori -> IshimoriRika)
        reversed_pascal_case_name = reverse_and_pascal_case(member_name_raw)

        # Sanitize the PascalCase name for use as a folder name
        member_subfolder_name = sanitize_name(reversed_pascal_case_name, is_folder=True)

        if not member_subfolder_name:
            status_callback("Error: Sanitized member name is empty.")
            return

        # Define the final target directory (e.g., images/IshimoriRika)
        target_folder = main_image_folder / member_subfolder_name

        # 2. Create the target directory
        target_folder.mkdir(parents=True, exist_ok=True)
        status_callback(f"Target folder set: {target_folder.as_posix()}")

        # 3. Find the main article container
        article_box = soup.find("div", class_="box-article")

        if article_box:
            status_callback("Searching for images...")
            image_tags = article_box.find_all("img")
            status_callback(f"Found {len(image_tags)} image tags.")

            # --- Download Images ---
            for i, img in enumerate(image_tags):
                relative_url = img.get("src") or img.get("data-src")

                if relative_url:
                    full_image_url = urljoin(base_url, relative_url)

                    url_path = urlparse(full_image_url).path
                    original_filename = Path(url_path).name
                    sanitized_name = sanitize_name(original_filename)

                    # Create the final path for saving the file
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

                    except requests.exceptions.RequestException as img_e:
                        status_callback(
                            f"  Error downloading {full_image_url}: {img_e}"
                        )
                    except Exception as save_e:
                        status_callback(
                            f"  Error saving file {filename.name}: {save_e}"
                        )
                else:
                    status_callback(f"  Image tag {i+1} has no valid source attribute.")

        else:
            status_callback("Element with the specified class 'box-article' not found.")

    except requests.exceptions.RequestException as e:
        status_callback(f"An error occurred during initial request: {e}")
    except Exception as e:
        status_callback(f"An unexpected error occurred: {e}")

    status_callback("---")
    status_callback("Image download process complete! ✅")


# --- GUI Implementation ---


class ImageDownloaderApp:
    def __init__(self, master):
        self.master = master
        master.title("Sakurazaka46 Image Downloader")
        master.geometry("500x400")  # Set initial window size

        # Default URL
        default_url = (
            "https://sakurazaka46.com/s/s46/diary/detail/66196?ima=0000&cd=blog"
        )

        # URL Input
        self.url_label = tk.Label(master, text="Enter Blog URL:")
        self.url_label.pack(pady=(10, 0))

        self.url_entry = tk.Entry(master, width=60)
        self.url_entry.insert(0, default_url)
        self.url_entry.pack(pady=5)

        # Download Button
        self.download_button = tk.Button(
            master,
            text="Start Download",
            command=self.run_download_in_thread,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        self.download_button.pack(pady=10)

        # Status Area Label
        self.status_label = tk.Label(master, text="Status/Log:", anchor="w")
        self.status_label.pack(fill="x", padx=10, pady=(5, 0))

        # Status Log Text Area
        self.log_text = tk.Text(master, height=15, width=60, state="disabled")
        self.log_text.pack(padx=10, pady=5)

    def update_status(self, message):
        """Adds a message to the log text area."""
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # Auto-scroll to the bottom
        self.log_text.config(state="disabled")
        self.master.update_idletasks()  # Ensure the GUI updates immediately

    def run_download_in_thread(self):
        """Starts the download function in a separate thread."""
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a valid URL.")
            return

        # Clear the log
        self.log_text.config(state="normal")
        self.log_text.delete(1.0, tk.END)
        self.log_text.config(state="disabled")

        self.download_button.config(state=tk.DISABLED, text="Downloading...")

        # Start the download function in a thread
        # We pass self.update_status as the status_callback
        thread = Thread(target=start_download_process, args=(url, self.update_status))
        thread.start()

        # Check thread status periodically to re-enable button
        self.check_thread(thread)

    def check_thread(self, thread):
        """Checks if the download thread is still alive."""
        if thread.is_alive():
            # If still running, check again in 100 milliseconds
            self.master.after(100, lambda: self.check_thread(thread))
        else:
            # If finished, re-enable the button
            self.download_button.config(state=tk.NORMAL, text="Start Download")


# --- Run the GUI ---
if __name__ == "__main__":
    root = tk.Tk()
    app = ImageDownloaderApp(root)
    root.mainloop()
