import requests
from bs4 import BeautifulSoup
from datetime import datetime


def download_report():
    session = requests.Session()

    # Step 1: Open the login page and extract CSRF token
    try:
        login_page = session.get("https://upepm.in/admin/login")
        soup = BeautifulSoup(login_page.text, "html.parser")
        
        token_input = soup.find("input", {"name": "_token"})
        if not token_input:
            return None, "Failed to find CSRF token"
            
        token = token_input["value"]

        # Step 2: Login using the extracted token
        payload = {
            "_token": token,
            "email": "upapprove",
            "password": "MEMI@1234"
        }

        resp = session.post("https://upepm.in/admin/login/logins", data=payload)
        
        # Step 3: Use the same session to download files
        current_date = datetime.now().strftime("%Y-%m-%d")
        download_url = f"https://upepm.in/admin/availablesupply/download-availability-report?date={current_date}&filter_type=combine"
        file_data = session.get(download_url)
        
        filename = f"Availability_Report_{current_date}.csv"
        with open(filename, "wb") as fd:
            fd.write(file_data.content)
            
        return filename, "Download complete!"
    except Exception as e:
        return None, str(e)

if __name__ == "__main__":
    file, msg = download_report()
    print(msg)
