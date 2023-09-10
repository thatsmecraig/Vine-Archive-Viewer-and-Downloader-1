import tkinter as tk
from tkinter import ttk, messagebox
import requests
from datetime import datetime
import webbrowser
import os
import re
import threading
import time
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TIT2


# Cache to store post data
post_data_cache = {}
post_data_lock = threading.Lock()

# Create and Write to the Log File
def write_to_log(log_path, message):
    with open(log_path, "a") as log_file:
        log_file.write(message + "\n")

def fetch_vine_data():
    global post_ids, total_posts, username, vine_data

    user_id = entry_user_id.get()

    if not user_id:
        messagebox.showwarning("Warning", "928514065121300480")
        return

    url = f"https://archive.vine.co/profiles/_/{user_id}.json"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            vine_data = response.json()
            display_vine_data(vine_data)
            post_ids = vine_data.get('posts', [])
            total_posts = vine_data.get('postCount', 0)
            username = vine_data.get('username', 'N/A')
            progress_bar["maximum"] = total_posts
            update_progress_label(0)
            button_download_all['state'] = tk.NORMAL
        else:
            messagebox.showerror("Error", f"Failed to fetch data. Status code: {response.status_code}")
    except requests.RequestException as e:
        messagebox.showerror("Error", f"An error occurred: {e}")

def fetch_post_data():
    tree.delete(*tree.get_children())
    thread = threading.Thread(target=fetch_all_post_data_thread)
    thread.start()

def fetch_all_post_data_thread():
    if not post_ids:
        messagebox.showwarning("Warning", "No posts found for this Vine user.")
        return

    progress_bar["value"] = 0

    for index, post_id in enumerate(post_ids, 1):
        post_data = load_post_data(post_id)
        if post_data is not None:
            display_post_data(post_data)
        else:
            # Skip the post and continue to the next one
            continue

        progress_bar["value"] = index
        update_progress_label(index)

def on_right_click(event):
    item = tree.identify('item', event.x, event.y)
    if item:
        column = tree.identify('column', event.x, event.y)
        if column == '#2': 
            context_menu.post(event.x_root, event.y_root)

def open_video_low_url():
    item = tree.selection()
    if item:
        url = tree.item(item, "values")[1]
        webbrowser.open(url)

def download_all_vines():
    folder_path = os.path.join(os.getcwd(), username)
    os.makedirs(folder_path, exist_ok=True)
    button_download_all['state'] = tk.DISABLED
    progress_bar["value"] = 0
    thread = threading.Thread(target=download_all_vines_thread, args=(folder_path,))
    thread.start()


def clean_foldername(foldername):
    return re.sub(r'[\\/*?:"<>|]', '', foldername)

def download_all_vines():
    folder_name = clean_foldername(username)
    folder_path = os.path.join(os.getcwd(), folder_name)
    os.makedirs(folder_path, exist_ok=True)
    button_download_all['state'] = tk.DISABLED

    delay_after_vines = 100
    delay_time = 4

    num_skipped_downloads = 0
    num_successful_downloads = 0

    for index, post_id in enumerate(post_ids, 1):
        post_data = load_post_data(post_id)
        if post_data:
            success = download_video(post_data, index, folder_path)
            if success:
                num_successful_downloads += 1
            else:
                num_skipped_downloads += 1
        else:
            num_skipped_downloads += 1
            continue

        # Show a message after every 100 vines
        if index % delay_after_vines == 0 and index < total_posts:
            message = f"Downloading paused for {delay_time} seconds to prevent server timeout.\nResuming after {delay_time} seconds..."
            messagebox.showinfo("Download Paused", message)
            time.sleep(delay_time)

    # After all vines are downloaded, write summary information to the log
    summary_message = (
        f"Download Summary:\n"
        f"Total Vines: {len(post_ids)}\n"
        f"Successful Downloads: {num_successful_downloads}\n"
        f"Skipped Downloads: {num_skipped_downloads}"
    )
    log_file_path = os.path.join(folder_path, f"{folder_name}.log")
    write_to_log(log_file_path, summary_message)

    button_download_all['state'] = tk.NORMAL

def update_progress_label(progress):
    progress_label["text"] = f"{progress}/{total_posts} Loaded Post"

def clean_filename(filename):
    return re.sub(r'[\\/*?:"<>|]', '', filename)

def download_video(post_data, index, folder_path):
    video_low_url = post_data.get('videoLowURL')
    if not video_low_url:
        # Show a warning message if video URL is null
        description = post_data.get('description', 'N/A')
        messagebox.showwarning("Warning", f"Vine: '{description}' has a null video URL. This may happen when the archiving state of Vine was being integrated, and the video URL got cut, or the video is long lost and corrupted since Vine shutdown.")
        return

    if video_low_url:
        description = post_data.get('description', 'N/A')
        description_cleaned = clean_filename(description)
        filename = f"{username}_vine_{description_cleaned}.mp4"
        filepath = os.path.join(folder_path, filename)

        try:
            response = requests.get(video_low_url)
            if response.status_code == 200:
                with open(filepath, 'wb') as file:
                    file.write(response.content)
                print(f"Video {index} downloaded successfully.")

                # Add created date to the video file's metadata
                post_created = post_data.get('created')
                if post_created:
                    created_datetime = datetime.strptime(post_created, "%Y-%m-%dT%H:%M:%S.%f")

                    # Use mutagen to update metadata
                    audio = MP4(filepath)
                    audio['\xa9day'] = created_datetime.strftime('%Y-%m-%d')
                    audio.save()

            else:
                print(f"Failed to download video {index}. Status code: {response.status_code}")
        except requests.RequestException as e:
            print(f"An error occurred while downloading video {index}: {e}")

def load_post_data(post_id):
    # Check if post data is already cached
    with post_data_lock:
        if post_id in post_data_cache:
            return post_data_cache[post_id]

    post_url = f"https://archive.vine.co/posts/{post_id}.json"
    try:
        post_response = requests.get(post_url)
        if post_response.status_code == 200:
            post_data = post_response.json()
            # Cache the post data for future use
            with post_data_lock:
                post_data_cache[post_id] = post_data
            return post_data
        elif post_response.status_code == 403:
            print(f"Skipped post_id {post_id} due to 403 Forbidden error.")
            return None
        else:
            messagebox.showerror("Error", f"Failed to fetch post data. Status code: {post_response.status_code}")
            return None
    except requests.RequestException as e:
        messagebox.showerror("Error", f"An error occurred while fetching post data: {e}")
        return None

def display_vine_data(vine_data):
    tree.delete(*tree.get_children())

    created = vine_data.get('created', 'N/A')
    created_datetime = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S.%f")
    created_human_readable = created_datetime.strftime('%Y-%m-%d %I:%M:%S %p')

    tree.insert("", "end", values=("Username", vine_data.get('username', 'N/A')))
    tree.insert("", "end", values=("Created", created_human_readable))
    tree.insert("", "end", values=("Status", vine_data.get('status', 'N/A')))
    tree.insert("", "end", values=("Post Count", vine_data.get('postCount', 'N/A')))

def display_post_data(post_data):
    tree.insert("", "end", values=("", "--------"), tags=("separator",))

    entities = post_data.get('entities', [])
    title = entities[0].get('title', 'N/A') if entities else 'N/A'
    video_low_url = post_data.get('videoLowURL', 'N/A')
    description = post_data.get('description', 'N/A')
    reposts = post_data.get('reposts', 'N/A')
    comments = post_data.get('comments', 'N/A')
    likes = post_data.get('likes', 'N/A')
    created = post_data.get('created', 'N/A')

    try:
        created_datetime = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S.%f")
    except ValueError:
        created_datetime = datetime.strptime(created, "%Y-%m-%dT%H:%M:%S")

    created_human_readable = created_datetime.strftime('%Y-%m-%d %I:%M:%S %p')

    tree.insert("", "end", values=("Title", title))
    tree.insert("", "end", values=("Video URL", video_low_url))
    tree.insert("", "end", values=("Description", description))
    tree.insert("", "end", values=("Reposts", reposts))
    tree.insert("", "end", values=("Comments", comments))
    tree.insert("", "end", values=("Likes", likes))
    tree.insert("", "end", values=("Created", created_human_readable))

def fetch_all_post_data():
    global post_data_cache
    # Clear existing data from Treeview
    tree.delete(*tree.get_children())

    if not post_ids:
        messagebox.showwarning("Warning", "No posts found for this Vine user.")
        return

    progress_bar["value"] = 0

    for index, post_id in enumerate(post_ids, 1):
        post_data = load_post_data(post_id)
        if post_data is not None:
            display_post_data(post_data)
        else:
            break

        # Update progress bar and label
        progress_bar["value"] = index
        update_progress_label(index)

# Create the main application window
root = tk.Tk()
root.title("Vine Archiver Viewer & Downloader")


vine_dark_gray = "#55BE96" 
vine_accent_color = "#55BE96"  


root.configure(background=vine_dark_gray)


style = ttk.Style()
style.theme_use('xpnative') 


style.configure('TEntry', background=vine_accent_color)

# Stretch the GUI to fill available space
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(0, weight=1)


frame_input = ttk.Frame(root)
frame_input.grid(row=0, column=0, padx=10, pady=5, sticky="ew")

label_user_id = ttk.Label(frame_input, text="Vine User ID:")
label_user_id.grid(row=0, column=0, sticky="w")

entry_user_id = ttk.Entry(frame_input, width=15)
entry_user_id.grid(row=0, column=1, padx=5, sticky="ew")

button_load_vine = ttk.Button(frame_input, text="Load Vine Data", command=fetch_vine_data)
button_load_vine.grid(row=0, column=2, padx=5, sticky="ew")

button_load_post = ttk.Button(frame_input, text="Load Post Data", command=fetch_post_data)
button_load_post.grid(row=0, column=3, padx=5, sticky="ew")

button_download_all = ttk.Button(frame_input, text="Download All Vines", command=download_all_vines)
button_download_all.grid(row=0, column=4, padx=5, sticky="ew")

# Create context menu
context_menu = tk.Menu(root, tearoff=0)
context_menu.add_command(label="Open", command=open_video_low_url)

# Bind right-click event to the Treeview
tree = ttk.Treeview(root, columns=("Property", "Data"), show="headings", height=10)
tree.heading("Property", text="Info")
tree.heading("Data", text="Data")
tree.bind("<Button-3>", on_right_click)  # Moved the bind here
tree.grid(row=1, column=0, padx=10, pady=(0, 5), sticky="nsew")

# Create Progress Bar
progress_bar = ttk.Progressbar(root, mode="determinate", length=300)
progress_bar.grid(row=2, column=0, pady=(0, 10), sticky="ew")

# Create Progress Label
progress_label = ttk.Label(root, text="0/0 Loaded Post")
progress_label.grid(row=3, column=0)

# Initialize post_ids and total_posts variables
post_ids = []
total_posts = 0
username = ''
vine_data = {}

# Start the main event loop
root.mainloop()
