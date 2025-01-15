import os
from tkinter import Tk, Label, Entry, Button, filedialog, StringVar
from download import download_arxiv_pdf, download_usenix_pdf, download_ieee_pdf

PLATFORMS = ["arXiv", "USENIX", "IEEE"]


def select_folder():
    """Open a folder dialog starting at W:\Papers."""
    folder = filedialog.askdirectory(initialdir=r"W:\Papers")  # Use raw string for path
    if folder:
        folder_path.set(folder)


def set_platform(platform):
    """Set the selected platform."""
    selected_platform.set(platform)
    print(f"Selected platform: {platform}")


def download_pdf(platform, url, download_folder):
    """Download the paper based on the selected platform."""
    try:
        if platform == "arXiv":
            download_arxiv_pdf(url, download_folder)
        elif platform == "USENIX":
            download_usenix_pdf(url, download_folder)
        elif platform == "IEEE":
            download_ieee_pdf(url, download_folder)
        else:
            print(f"Unsupported platform: {platform}")
    except Exception as e:
        print(f"Error downloading paper: {e}")


def start_download():
    """Start the download process."""
    platform = selected_platform.get()
    url = url_entry.get()
    download_folder = folder_path.get()

    if platform and url and download_folder:
        download_pdf(platform, url, download_folder)
    else:
        print("Please select a platform, provide a URL, and choose a download folder.")


# Set up GUI
root = Tk()
root.title("Research Paper Downloader")

selected_platform = StringVar(root)  # Create StringVar after root is initialized
selected_platform.set("")  # Initialize with empty value

Label(root, text="Select Platform").grid(row=0, column=0, columnspan=2)

# Buttons for platform selection
for i, platform in enumerate(PLATFORMS):
    Button(root, text=platform, command=lambda p=platform: set_platform(p)).grid(row=1, column=i)

Label(root, text="URL").grid(row=2, column=0)
url_entry = Entry(root, width=50)
url_entry.grid(row=2, column=1, columnspan=3)

Label(root, text="Download Folder").grid(row=3, column=0)
folder_path = StringVar(root)  # Create StringVar after root is initialized
Button(root, text="Select Folder", command=select_folder).grid(row=3, column=1, columnspan=3)

Button(root, text="Download", command=start_download).grid(row=4, column=1, columnspan=2)

root.mainloop()
