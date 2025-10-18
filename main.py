import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from pathlib import Path
import re
import sys

# --- Setup ---
url = "https://sakurazaka46.com/s/s46/diary/detail/66196?ima=0000&cd=blog"
base_url = "https://sakurazaka46.com"
main_image_folder = Path("images")

# --- Utility Functions ---


def to_pascal_case(text):
    """Converts a string (like 'moriya rena') to PascalCase (like 'MoriyaRena')."""
    if not text:
        return ""
    # Split by spaces, hyphens, and underscores, then capitalize each word and join.
    return "".join(word.capitalize() for word in re.split(r"[\s\-_]+", text.lower()))


def sanitize_name(name, is_folder=False):
    """Remove illegal characters and query strings from a filename or folder name."""
    # Remove query parameters (e.g., ?ima=0000)
    name = name.split("?")[0]
    # For folders, replace non-word characters with nothing, leaving a clean name.
    if is_folder:
        name = re.sub(r"[^\w]", "", name).strip()
    # For files, replace non-word characters with an underscore.
    else:
        name = re.sub(r"[^\w\-\.]", "_", name)
    return name


# --- Fetch HTML Content ---

try:
    print(f"Fetching URL: {url}...")
    response = requests.get(url, timeout=15)
    response.raise_for_status()
    html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")

    # 1. Get the subfolder name from <p class="eigo wf-a">
    p_tag = soup.find("p", class_="eigo wf-a")
    if not p_tag:
        print(
            'Error: English name (<p class="eigo wf-a">) not found. Cannot create subfolder.'
        )
        sys.exit(1)

    member_name_raw = p_tag.get_text(strip=True)

    # Convert to PascalCase (e.g., moriya rena -> MoriyaRena)
    pascal_case_name = to_pascal_case(member_name_raw)

    # Sanitize the PascalCase name for use as a folder name
    member_subfolder_name = sanitize_name(pascal_case_name, is_folder=True)

    if not member_subfolder_name:
        print("Error: Sanitized member name is empty. Cannot create subfolder.")
        sys.exit(1)

    # Define the final target directory (e.g., images/MoriyaRena)
    target_folder = main_image_folder / member_subfolder_name

    # 2. Create the target directory
    target_folder.mkdir(parents=True, exist_ok=True)
    print(f"Target folder set: {target_folder}")

    # 3. Find the main article container
    article_box = soup.find("div", class_="box-article")

    if article_box:
        print("Article container found. Searching for images...")

        # --- Find all image tags within the 'box-article' ---
        image_tags = article_box.find_all("img")
        print(f"Found {len(image_tags)} image tags.")

        # --- Download Images ---
        for i, img in enumerate(image_tags):
            relative_url = img.get("src") or img.get("data-src")

            if relative_url:
                full_image_url = urljoin(base_url, relative_url)

                # Use the path part of the URL for a base filename
                url_path = urlparse(full_image_url).path

                original_filename = Path(url_path).name
                sanitized_name = sanitize_name(original_filename)

                # Create the final path for saving the file inside the new subfolder
                filename = target_folder / f"{i+1:02d}_{sanitized_name}"

                # Ensure a common image extension if none is found
                if not filename.suffix:
                    filename = filename.with_suffix(".jpg")

                # Download the image content
                try:
                    img_response = requests.get(full_image_url, stream=True, timeout=15)
                    img_response.raise_for_status()

                    # Save the image to the file
                    with filename.open("wb") as f:
                        for chunk in img_response.iter_content(chunk_size=8192):
                            f.write(chunk)

                    print(f"  Downloaded: {filename.name}")

                except requests.exceptions.RequestException as img_e:
                    print(f"  Error downloading {full_image_url}: {img_e}")
                except Exception as save_e:
                    print(f"  Error saving file {filename}: {save_e}")
            else:
                print(f"  Image tag {i+1} has no valid source attribute.")

    else:
        print("Element with the specified class 'box-article' not found.")

except requests.exceptions.RequestException as e:
    print(f"An error occurred during initial request: {e}")

print("---")
print("Image download process complete.")
