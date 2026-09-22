import os
import time
import requests
import datetime
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from pathlib import Path

LOGIN_URL = "https://myrtpos.com/newbdi/index.fwx"
REPORT_URL = "https://myrtpos.com/newbdi/Store_Performance_lp.fwx"

FINAL_COLUMNS = [
    'SAP ID', 'Store ID', 'Hours', 'Boxes', 'New All', 'New Voice', 
    'Upg', 'React.', 'PPD', 'Box/Hr', 'Acc $', 'Acc Qty', 'Acc/PPD', 'Acc/Box', 
    'QPAY', 'Conv %', 'Base MRC', 'Feature Rev', 'MLS', 'AAL', 'HSPT', 'SR', 
    'Tablet', 'Pet', 'Tmx', 'BTS', 'PSB', 'Trade', 'HINT', 'Watch', 'Month'
]

def login(username, password, progress_fn=None):
    if progress_fn: progress_fn("Authenticating with RTPOS...")
    
    session = requests.Session()
    initial_response = session.get(LOGIN_URL, timeout=30)
    soup = BeautifulSoup(initial_response.text, 'html.parser')
    session_id_input = soup.find('input', {'name': 'secSessionID'})
    
    if not session_id_input:
        raise ConnectionError("Could not reach the login page.")
        
    login_payload = {
        "secSessionID": session_id_input['value'],
        "secUserID": username, 
        "secPassword": password,
        "secSaveCookie": "1"
    }
    
    login_response = session.post(LOGIN_URL, data=login_payload, timeout=30)
    if "secUserID" in login_response.text:
        raise PermissionError("Login failed! Verify credentials.")
    
    time.sleep(3) # FWX stabilization delay[cite: 10]
    return session

def download_daily_report(session, target_date: datetime.date, workspace_dir: Path, progress_fn=None):
    target_date_str = target_date.strftime("%m/%d/%Y")
    
    payload = {
        "frmMarketID": "", "frmRegionID": "", "frmStateID": "",
        "frmStoreType": "", "frmStore": "",
        "frmStart": target_date_str, "frmEnd": target_date_str,
        "btnExcel": "click", 
    }
    
    max_attempts = 5
    backoff_delays = [5, 10, 20, 40]
    prev_rows, prev_size, prev_file = -1, -1, None
    
    for attempt in range(1, max_attempts + 1):
        if progress_fn: progress_fn(f"Downloading {target_date_str} (Attempt {attempt}/{max_attempts})")
        
        response = session.post(REPORT_URL, data=payload, timeout=60)
        
        if response.status_code != 200 or "secUserID" in response.text:
            raise ConnectionError("Session dropped during download.")
            
        filename = f"temp_metro_{target_date.strftime('%Y%m%d')}_v{attempt}.xls"
        full_path = workspace_dir / filename
        
        with open(full_path, "wb") as f:
            f.write(response.content)
            
        current_size = full_path.stat().st_size
        try:
            current_rows = len(pd.read_excel(full_path, engine="xlrd"))
        except Exception:
            current_rows = 0

        # Stable download verification[cite: 10]
        if attempt > 1 and current_rows == prev_rows and current_size == prev_size and current_rows > 0:
            if prev_file and prev_file.exists():
                prev_file.unlink()
            return full_path
            
        prev_rows, prev_size = current_rows, current_size
        if prev_file and prev_file.exists():
            prev_file.unlink()
        prev_file = full_path
        
        if attempt < max_attempts:
            time.sleep(backoff_delays[attempt - 1])
            
    raise Exception(f"Failed to achieve a stable download for {target_date_str}.")

def process_data(raw_file_path: Path, target_date: datetime.date):
    df = pd.read_excel(raw_file_path, engine="xlrd")
    df = df.dropna(subset=['sapid']) 
    
    report = pd.DataFrame()
    report['SAP ID'] = df['sapid'].astype(int).astype(str)
    report['Store ID'] = df['marketid'] + " " + df['custno'].astype(str) + " -" + df['company']
    report['Hours'] = df['hoursworked']
    report['Boxes'] = df['phoneinv']
    report['New All'] = df['newact']
    report['BTS'] = df['iot']
    
    report['New Voice'] = report['New All'] - report['BTS']
    report['Upg'] = df['upgsor']
    report['React.'] = df['reactact']
    report['PPD'] = df['totact']
    report['Box/Hr'] = df['boxperhour']
    report['Acc $'] = df['totaccessory']
    report['Acc Qty'] = df['totaccessoryqty']

    report['Acc/PPD'] = np.where(report['PPD'] > 0, report['Acc $'] / report['PPD'], 0)
    report['Acc/Box'] = np.where(report['Boxes'] > 0, report['Acc $'] / report['Boxes'], 0)

    report['QPAY'] = df['totpaymentqty']
    report['Conv %'] = np.where(report['QPAY'] > 0, (report['PPD'] / report['QPAY']), 0)
    
    report['Base MRC'] = df['avgmrc']
    feature_denom = report['New Voice'] + report['React.']
    report['Feature Rev'] = np.where(feature_denom > 0, df['featuremrc'] / feature_denom, 0)

    report['MLS'] = df['mls']
    report['AAL'] = df['aal']
    report['HSPT'] = df['linkzone']
    report['SR'] = df['smartcar']
    report['Tablet'] = df['tablet']
    report['Pet'] = df['pettracker']
    report['Tmx'] = df['timex']
    report['PSB'] = df['psb']
    report['Trade'] = df['ticount']
    report['HINT'] = df['hint']
    report['Watch'] = df['watch']
    
    report['Month'] = target_date

    return report[FINAL_COLUMNS]

def execute_metro_kpi(username, password, date_list, workspace_dir: Path, progress_callback=None):
    session = login(username, password, lambda msg: progress_callback(0, len(date_list), msg) if progress_callback else None)
    
    all_dataframes = []
    
    for i, target_date in enumerate(date_list, start=1):
        if progress_callback:
            progress_callback(i, len(date_list), f"Processing data for {target_date.strftime('%b %d')}...")
            
        raw_path = download_daily_report(session, target_date, workspace_dir, 
                                         lambda msg: progress_callback(i, len(date_list), msg) if progress_callback else None)
        
        daily_df = process_data(raw_path, target_date)
        all_dataframes.append(daily_df)
        
        if raw_path.exists():
            raw_path.unlink()
            
    if not all_dataframes:
        raise ValueError("No data was processed.")
        
    final_df = pd.concat(all_dataframes, ignore_index=True)
    return final_df