import imaplib
import email
from email.header import decode_header
import time
import os
from pathlib import Path

# Folder where attachments will be saved
INCOMING_DIR = "data/incoming"

# EMAIL MONITOR CONFIGURATION
EMAIL_HOST = "imap.gmail.com"           # IMAP host (Gmail, Outlook, etc.)
EMAIL_USER = "abc@gmail.com"      # Your email address
EMAIL_PASS = "abcd efgh ijkl mnop"        # Use app password, NOT normal password
EMAIL_CHECK_INTERVAL = 10               # Check interval (in seconds)
VALID_EXTENSIONS = ('.pdf', '.docx', '.png', '.jpg', '.jpeg')


def _normalize_incoming_dir(p) -> Path:
    """Ensure absolute incoming directory path exists."""
    path = Path(p).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_attachment(part, filename, incoming_path):
    """Save a single attachment to the incoming folder."""
    filepath = os.path.join(incoming_path, filename)
    with open(filepath, "wb") as f:
        f.write(part.get_payload(decode=True))
    print(f"📎 Saved attachment: {filename}")


def get_last_email_uid(mail):
    """Get the UID of the most recent email when script starts."""
    status, data = mail.uid("search", None, "ALL")
    if status != "OK" or not data or not data[0]:
        return 0
    latest_uid = int(data[0].split()[-1])
    return latest_uid


def process_incoming_emails():
    """Monitor mailbox for *new* emails with 'invoice' in subject (ignore old ones)."""
    incoming_path = _normalize_incoming_dir(INCOMING_DIR)
    print(f"📨 Email monitor started... Checking every {EMAIL_CHECK_INTERVAL}s")

    processed_uids = set()
    saved_files = set()

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # 🟢 Step 1: Record all current UIDs as 'seen' so old mails are ignored
        status, data = mail.uid("search", None, "ALL")
        if status == "OK" and data and data[0]:
            processed_uids = {int(x) for x in data[0].split()}
        print(f"✅ Ignoring {len(processed_uids)} existing emails. Waiting for new ones...")

        while True:
            try:
                # 🟡 Step 2: Fetch all UIDs again and find which ones are new
                status, data = mail.uid("search", None, "ALL")
                if status != "OK" or not data or not data[0]:
                    time.sleep(EMAIL_CHECK_INTERVAL)
                    continue

                current_uids = {int(x) for x in data[0].split()}
                new_uids = sorted(current_uids - processed_uids)

                # 🟠 Step 3: Process only new UIDs
                if new_uids:
                    print(f"\n📬 Found {len(new_uids)} new email(s)")
                    for uid in new_uids:
                        status, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
                        if status != "OK" or not msg_data or not msg_data[0]:
                            continue

                        msg = email.message_from_bytes(msg_data[0][1])
                        raw_subject = msg.get("Subject", "")
                        subject, encoding = decode_header(raw_subject)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        subject_lower = subject.lower().strip() if subject else ""

                        # ✅ Only process subjects containing 'invoice'
                        if "invoice" not in subject_lower:
                            print(f"⏩ Skipped (subject not invoice): {subject}")
                            processed_uids.add(uid)
                            continue

                        print(f"📩 New Invoice Email: {subject}")

                        # 🧩 Save valid attachments
                        for part in msg.walk():
                            if part.get_content_disposition() == "attachment":
                                filename = part.get_filename()
                                if not filename:
                                    continue
                                ext = os.path.splitext(filename)[1].lower()
                                if ext not in VALID_EXTENSIONS:
                                    continue

                                target = os.path.join(incoming_path, filename)
                                if filename in saved_files or os.path.exists(target):
                                    continue

                                save_attachment(part, filename, incoming_path)
                                saved_files.add(filename)

                        processed_uids.add(uid)

                time.sleep(EMAIL_CHECK_INTERVAL)

            except imaplib.IMAP4.abort:
                print("⚠️ Connection lost. Reconnecting...")
                time.sleep(5)
                mail = imaplib.IMAP4_SSL(EMAIL_HOST)
                mail.login(EMAIL_USER, EMAIL_PASS)
                mail.select("inbox")

            except Exception as e:
                print(f"[EmailMonitor] Error: {e}")
                time.sleep(5)

    except Exception as e:
        print(f"❌ Could not connect to mailbox: {e}")
    """Continuously monitor mailbox for new emails with 'invoice' in subject."""
    incoming_path = _normalize_incoming_dir(INCOMING_DIR)
    print(f"📨 Email monitor started... Checking every {EMAIL_CHECK_INTERVAL}s")

    processed_uids = set()   # UIDs we've already processed
    saved_files = set()

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        # Initialize processed_uids to whatever is already in the mailbox so we only handle future messages
        status, data = mail.uid("search", None, "ALL")
        if status == "OK" and data and data[0]:
            existing = [int(x) for x in data[0].split()]
            processed_uids.update(existing)
        print(f"Starting with {len(processed_uids)} existing message(s) known.")

        while True:
            try:
                # Get all UIDs each cycle and compute the difference
                status, data = mail.uid("search", None, "ALL")
                if status != "OK" or not data or not data[0]:
                    time.sleep(EMAIL_CHECK_INTERVAL)
                    continue

                all_uids = [int(x) for x in data[0].split()]
                # find uids that are not yet processed
                new_uids = sorted(uid for uid in all_uids if uid not in processed_uids)
                if new_uids:
                    print(f"\n📬 Found {len(new_uids)} new email(s)")
                    for uid in new_uids:
                        status, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
                        if status != "OK" or not msg_data or not msg_data[0]:
                            continue

                        msg = email.message_from_bytes(msg_data[0][1])
                        raw_subject = msg.get("Subject", "")
                        subject, encoding = decode_header(raw_subject)[0]
                        if isinstance(subject, bytes):
                            subject = subject.decode(encoding or "utf-8", errors="ignore")
                        subject_lower = subject.lower().strip() if subject else ""

                        # Filter only invoice subjects
                        if "invoice" not in subject_lower:
                            print(f"⏩ Skipped (subject not invoice): {subject}")
                            processed_uids.add(uid)
                            continue

                        print(f"📩 New Invoice Email: {subject}")

                        # Save attachments with valid extensions
                        for part in msg.walk():
                            if part.get_content_disposition() == "attachment":
                                filename = part.get_filename()
                                if not filename:
                                    continue
                                ext = os.path.splitext(filename)[1].lower()
                                if ext not in VALID_EXTENSIONS:
                                    continue

                                target = os.path.join(incoming_path, filename)
                                # Skip if we've already saved this file before
                                if filename in saved_files or os.path.exists(target):
                                    print(f"🔁 Already saved, skipping: {filename}")
                                    continue

                                save_attachment(part, filename, incoming_path)
                                saved_files.add(filename)

                        # mark uid processed
                        processed_uids.add(uid)

                time.sleep(EMAIL_CHECK_INTERVAL)

            except imaplib.IMAP4.abort:
                print("⚠️ Connection lost. Reconnecting...")
                time.sleep(5)
                mail = imaplib.IMAP4_SSL(EMAIL_HOST)
                mail.login(EMAIL_USER, EMAIL_PASS)
                mail.select("inbox")

            except Exception as e:
                print(f"[EmailMonitor] Error: {e}")
                time.sleep(5)

    except Exception as e:
        print(f"❌ Could not connect to mailbox: {e}")
    """Continuously monitor mailbox for new emails with 'invoice' in subject."""
    incoming_path = _normalize_incoming_dir(INCOMING_DIR)
    print(f"📨 Email monitor started... Checking every {EMAIL_CHECK_INTERVAL}s")

    processed_uids = set()
    saved_files = set()

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        last_seen_uid = get_last_email_uid(mail)
        print(f"Starting from UID: {last_seen_uid}")

        while True:
            try:
                # Fetch only new emails after the last seen UID
                status, data = mail.uid("search", None, f"(UID {last_seen_uid + 1}:*)")
                if status == "OK" and data and data[0]:
                    new_uids = [int(uid) for uid in data[0].split()]
                    if new_uids:
                        new_uids = [uid for uid in new_uids if uid not in processed_uids]
                        if not new_uids:
                            time.sleep(EMAIL_CHECK_INTERVAL)
                            continue

                        print(f"\n📬 Found {len(new_uids)} new email(s)")
                        for uid in new_uids:
                            status, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
                            if status != "OK":
                                continue

                            msg = email.message_from_bytes(msg_data[0][1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")
                            subject_lower = subject.lower().strip() if subject else ""

                            # ✅ Filter: Only process if subject contains 'invoice'
                            if "invoice" not in subject_lower:
                                last_seen_uid = uid
                                processed_uids.add(uid)
                                continue

                            print(f"📩 New Invoice Email: {subject}")

                            # Save attachments with valid extensions
                            for part in msg.walk():
                                if part.get_content_disposition() == "attachment":
                                    filename = part.get_filename()
                                    if not filename:
                                        continue
                                    ext = os.path.splitext(filename)[1].lower()
                                    if ext not in VALID_EXTENSIONS:
                                        continue

                                    # ✅ Skip if file already saved
                                    if filename in saved_files or os.path.exists(os.path.join(incoming_path, filename)):
                                        continue

                                    save_attachment(part, filename, incoming_path)
                                    saved_files.add(filename)

                            last_seen_uid = uid
                            processed_uids.add(uid)

                time.sleep(EMAIL_CHECK_INTERVAL)

            except imaplib.IMAP4.abort:
                print("⚠️ Connection lost. Reconnecting...")
                time.sleep(5)
                mail = imaplib.IMAP4_SSL(EMAIL_HOST)
                mail.login(EMAIL_USER, EMAIL_PASS)
                mail.select("inbox")

            except Exception as e:
                print(f"[EmailMonitor] Error: {e}")
                time.sleep(5)

    except Exception as e:
        print(f"❌ Could not connect to mailbox: {e}")
    """Continuously monitor mailbox for new emails with 'invoice' in subject."""
    incoming_path = _normalize_incoming_dir(INCOMING_DIR)
    print(f"📨 Email monitor started... Checking every {EMAIL_CHECK_INTERVAL}s")

    try:
        mail = imaplib.IMAP4_SSL(EMAIL_HOST)
        mail.login(EMAIL_USER, EMAIL_PASS)
        mail.select("inbox")

        last_seen_uid = get_last_email_uid(mail)
        print(f"Starting from UID: {last_seen_uid}")

        while True:
            try:
                # Fetch only new emails after the last seen UID
                status, data = mail.uid("search", None, f"(UID {last_seen_uid + 1}:*)")
                if status == "OK" and data and data[0]:
                    new_uids = [int(uid) for uid in data[0].split()]
                    if new_uids:
                        print(f"\n📬 Found {len(new_uids)} new email(s)")
                        for uid in new_uids:
                            status, msg_data = mail.uid("fetch", str(uid), "(RFC822)")
                            if status != "OK":
                                continue

                            msg = email.message_from_bytes(msg_data[0][1])
                            subject, encoding = decode_header(msg["Subject"])[0]
                            if isinstance(subject, bytes):
                                subject = subject.decode(encoding or "utf-8")
                            subject_lower = subject.lower().strip() if subject else ""

                            # ✅ Filter: Only process if subject contains 'invoice'
                            if "invoice" not in subject_lower:
                                print(f"⏩ Skipped (subject not invoice): {subject}")
                                last_seen_uid = uid
                                continue

                            print(f"📩 New Invoice Email: {subject}")

                            # Save attachments with valid extensions
                            for part in msg.walk():
                                if part.get_content_disposition() == "attachment":
                                    filename = part.get_filename()
                                    if not filename:
                                        continue
                                    ext = os.path.splitext(filename)[1].lower()
                                    if ext not in VALID_EXTENSIONS:
                                        continue
                                    save_attachment(part, filename, incoming_path)

                            last_seen_uid = uid  # update last processed UID

                time.sleep(EMAIL_CHECK_INTERVAL)

            except imaplib.IMAP4.abort:
                print("⚠️ Connection lost. Reconnecting...")
                time.sleep(5)
                mail = imaplib.IMAP4_SSL(EMAIL_HOST)
                mail.login(EMAIL_USER, EMAIL_PASS)
                mail.select("inbox")

            except Exception as e:
                print(f"[EmailMonitor] Error: {e}")
                time.sleep(5)

    except Exception as e:
        print(f"❌ Could not connect to mailbox: {e}")


if __name__ == "__main__":
    process_incoming_emails()