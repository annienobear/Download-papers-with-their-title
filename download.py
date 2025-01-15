import os
import re
import time

import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def sanitize_filename(title):
    """Sanitizes the title to make it a valid filename."""
    # Remove invalid characters and replace newlines with a space
    sanitized_title = re.sub(r'[\\/*?:"<>|]', '_', title)
    sanitized_title = sanitized_title.replace('\n', ' ').replace('\r', ' ')
    return sanitized_title.strip()



def extract_arxiv_id(url):
    """Extracts the ArXiv ID from a given URL."""
    parsed_url = urlparse(url)
    path_parts = parsed_url.path.strip("/").split("/")
    if "abs" in path_parts:
        return path_parts[-1]  # Return the last part after 'abs'
    raise ValueError("Invalid ArXiv URL")


def get_pdf_title(arxiv_id):
    """Fetches the title of the paper from the ArXiv metadata."""
    metadata_url = f"https://export.arxiv.org/api/query?id_list={arxiv_id}"
    response = requests.get(metadata_url)
    response.raise_for_status()  # Raise an error if the request failed

    # Extract the title from the returned XML
    match = re.search(r"<title>(.*?)</title>", response.text, re.DOTALL)
    if match:
        return match.group(1).strip()
    else:
        raise ValueError("Failed to extract title from ArXiv metadata")


def wait_for_download_and_rename(download_folder, new_filename, timeout=30):
    existing_files = set(os.listdir(download_folder))
    end_time = time.time() + timeout

    while time.time() < end_time:
        current_files = set(os.listdir(download_folder))
        new_files = current_files - existing_files
        for file_name in new_files:
            # IEEE might name the file getPDF.jsp (or sometimes .pdf)
            if file_name.lower().endswith(".jsp") or file_name.lower().endswith(".pdf"):
                old_path = os.path.join(download_folder, file_name)
                new_path = os.path.join(download_folder, new_filename)
                os.rename(old_path, new_path)
                print(f"Renamed '{file_name}' to '{new_filename}'")
                return
        time.sleep(1)

    raise TimeoutError(f"No new downloaded JSP/PDF file found in {download_folder} within {timeout} seconds.")


def download_ieee_pdf(url, download_folder):
    """Downloads the PDF of an IEEE paper using Selenium and clicks the 'Open' button."""
    options = uc.ChromeOptions()

    # 1) Configure Chrome to automatically download PDFs
    prefs = {
        "download.default_directory": download_folder,
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
        # Try removing the built-in PDF viewer
        "plugins.plugins_list": [{"enabled": False, "name": "Chrome PDF Viewer"}],
    }
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-print-preview")
    options.add_argument("--kiosk-printing")

    # Attempt to disable the Chrome PDF plugin
    options.add_argument("--disable-pdf-material-ui")
    options.add_argument("--disable-extensions-file-access-check")
    options.add_experimental_option("prefs", prefs)

    # 2) Some additional flags that help avoid detection
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = uc.Chrome(options=options)

    try:
        # Step A: Load the main IEEE page
        driver.get(url)
        time.sleep(2)  # Let initial page elements load

        # Step B: Grab title
        title_element = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "h1.document-title.text-2xl-md-lh span"))
        )
        paper_title = title_element.text.strip()
        sanitized_title = sanitize_filename(paper_title)
        print("Found paper title:", sanitized_title)

        # Step C: Click the PDF link
        pdf_link_element = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//a[span[text()='PDF']]"))
        )
        pdf_link_element.click()

        all_iframes = driver.find_elements(By.TAG_NAME, "iframe")
        print("Found", len(all_iframes), "iframes:")

        stamp_iframe = None
        for iframe in all_iframes:
            src = iframe.get_attribute("src")
            print("iframe src:", src)
            if src and "stampPDF/getPDF.jsp" in src:
                stamp_iframe = iframe
                break

        if stamp_iframe:
            iframe_src = stamp_iframe.get_attribute("src")
            print("stamp iframe src:", iframe_src)
        else:
            raise Exception("Could not find the 'stampPDF' iframe")
        print("iframe src:", iframe_src)

        # 4) Get Selenium's cookies
        selenium_cookies = driver.get_cookies()

        for c in selenium_cookies:
            print(c)

        # 5) Build a requests session with those cookies
        session = requests.Session()
        for c in selenium_cookies:
            session.cookies.set(c['name'], c['value'], domain=c['domain'])

        # 6) Add typical headers, including Referer
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
            "Referer": "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=8835233",
            "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            # Occasionally helpful:
            # "Sec-Fetch-Dest": "iframe",
            # "Sec-Fetch-Mode": "navigate",
            # "Sec-Fetch-Site": "same-origin",
            # "Sec-Fetch-User": "?1",
        }

        # 7) Download the actual PDF
        r = session.get(iframe_src, headers=headers, allow_redirects=True)
        if r.status_code == 200 and b"%PDF" in r.content[:10]:
            # 8) Save to disk
            pdf_path = os.path.join(download_folder, sanitized_title + ".pdf")
            with open(pdf_path, "wb") as f:
                f.write(r.content)
            print(f"PDF saved to {pdf_path}")
        else:
            print("Could not retrieve a valid PDF. HTTP status:", r.status_code)
            print("First bytes:", r.content[:200])

    except Exception as e:
        print(f"Error during download: {e}")

    finally:
        driver.quit()


def download_usenix_pdf(url, download_folder):
    """Downloads the PDF of a USENIX paper."""
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "lxml")

    # Extract the paper title (assume first <h1> tag is the title)
    title_element = soup.find("h1")
    if not title_element:
        raise ValueError("Failed to extract title from USENIX page")

    paper_title = title_element.text.strip()
    sanitized_title = sanitize_filename(paper_title)

    # Find the specific PDF link (the first valid .pdf link)
    pdf_element = soup.find("a", href=re.compile(r".*\.pdf$"))
    if not pdf_element:
        raise ValueError("Failed to find PDF link on USENIX page")

    pdf_url = pdf_element["href"]
    if not pdf_url.startswith("http"):
        pdf_url = "https://www.usenix.org" + pdf_url

    # Download the PDF
    response = requests.get(pdf_url, headers=headers, stream=True)
    response.raise_for_status()

    pdf_path = os.path.join(download_folder, sanitized_title + ".pdf")
    with open(pdf_path, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                pdf_file.write(chunk)

    print(f"Downloaded: {pdf_path}")


def download_arxiv_pdf(url, download_folder):
    """Downloads the PDF of an ArXiv paper."""
    arxiv_id = extract_arxiv_id(url)
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

    # Fetch the paper title for naming the PDF
    paper_title = get_pdf_title(arxiv_id)
    sanitized_title = sanitize_filename(paper_title)

    # Download the PDF
    response = requests.get(pdf_url, stream=True)
    response.raise_for_status()  # Raise an error if the request failed

    pdf_path = os.path.join(download_folder, sanitized_title + ".pdf")
    with open(pdf_path, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=1024):
            if chunk:
                pdf_file.write(chunk)

    print(f"Downloaded: {pdf_path}")


# Example usage
# download_arxiv_pdf("https://arxiv.org/abs/2406.10109", "W:/Papers/system")
# download_usenix_pdf("https://www.usenix.org/conference/usenixsecurity19/presentation/staicu", "W:/Papers/system")
# download_ieee_pdf("https://ieeexplore.ieee.org/document/8835233", "W:/Papers/system")