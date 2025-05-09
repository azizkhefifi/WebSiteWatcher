import requests
import time
import os
import difflib
import threading
from bs4 import BeautifulSoup
import customtkinter as ctk
from tkinter import messagebox, filedialog
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import re
from urllib.parse import urlparse

# Configuration de la journalisation
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Initialize tasks_monitored_urls from file if it exists, otherwise use default
def load_monitored_urls():
    """Load monitored URLs from a file."""
    file_path = os.path.join(os.getcwd(), "monitored_urls.json")
    if os.path.exists(file_path):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading monitored URLs: {e}")
    return []

def save_monitored_urls(urls):
    """Save monitored URLs to a file."""
    file_path = os.path.join(os.getcwd(), "monitored_urls.json")
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(urls, f, indent=4)
    except Exception as e:
        print(f"Error saving monitored URLs: {e}")

# Load monitored URLs from file
tasks_monitored_urls = load_monitored_urls()

# Utility Functions
def fetch_html(url):
    session = requests.Session()
    retries = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    try:
        response = session.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        logging.error(f"Fetch error: {e}")
        raise Exception(f"Erreur de récupération de l'URL: {e}")

def modify_html(html, excluded_indices):
    soup = BeautifulSoup(html, 'html.parser')
    for idx, tag in enumerate(soup.find_all()):
        if idx in excluded_indices:
            tag.decompose()
    return str(soup)

def generate_diff(base_html, mod_html, diff_path):
    """Generate a diff between two HTML contents and save it to a file."""
    try:
        # Convert to strings if they're not already
        base_html = str(base_html)
        mod_html = str(mod_html)
        
        # Generate the diff
        diff = list(difflib.unified_diff(
            base_html.splitlines(), 
            mod_html.splitlines(), 
            lineterm='',
            fromfile='original',
            tofile='modified'
        ))
        
        # Write the diff to the file
        if diff:
            with open(diff_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(diff))
            return True
        else:
            # Create an empty file to indicate no changes
            with open(diff_path, 'w', encoding='utf-8') as f:
                f.write("No changes detected.")
            return False
    except Exception as e:
        logging.error(f"Error generating diff: {e}")
        # Create a file with the error message
        with open(diff_path, 'w', encoding='utf-8') as f:
            f.write(f"Error generating diff: {e}")
        return False

# GUI Classes
class TagSelector(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.checkboxes = []
        self.tag_indices = []
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.scrollable_frame = ctk.CTkScrollableFrame(self, label_text="Explorateur de Balises HTML")
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew")
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

    def clear_tags(self):
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()
        self.checkboxes = []
        self.tag_indices = []

    def add_tag(self, index, tag_name, attributes):
        frame = ctk.CTkFrame(self.scrollable_frame)
        frame.pack(fill="x", pady=2)
        var = ctk.BooleanVar()
        chk = ctk.CTkCheckBox(frame, variable=var, width=20)
        chk.pack(side="left", padx=5)
        self.checkboxes.append(var)
        self.tag_indices.append(index)
        info_text = f"Index: {index} | Balise: <{tag_name}>"
        if attributes:
            attrs = ", ".join(f"{k}={v}" for k,v in attributes.items() if v)
            info_text += f" | Attributs: {attrs}"
        label = ctk.CTkLabel(frame, text=info_text, anchor="w")
        label.pack(side="left", fill="x", expand=True)

    def get_selected_indices(self):
        return [self.tag_indices[i] for i,var in enumerate(self.checkboxes) if var.get()]

class LoadingScreen(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Chargement")
        self.geometry("300x150")
        self.transient(parent)
        self.grab_set()
        
        # Center the window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        # Create loading label
        self.loading_label = ctk.CTkLabel(self, text="Chargement des balises...", font=("Arial", 14))
        self.loading_label.pack(pady=20)
        
        # Create progress bar
        self.progress_bar = ctk.CTkProgressBar(self, width=200)
        self.progress_bar.pack(pady=10)
        self.progress_bar.set(0)
        
        # Create status label
        self.status_label = ctk.CTkLabel(self, text="", font=("Arial", 12))
        self.status_label.pack(pady=10)
        
    def update_progress(self, value, status_text=""):
        self.progress_bar.set(value)
        if status_text:
            self.status_label.configure(text=status_text)
        self.update_idletasks()

class WebMonitorApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Moniteur Web Avancé")
        self.geometry("1200x800")
        self.current_html = ""
        self.current_url = None
        self.current_danger_level = None
        
        # Dictionary to track multiple monitoring threads: {url: (thread, stop_event)}
        self.monitoring_threads = {}
        
        self.monitored_urls = tasks_monitored_urls
        self.danger_levels = ["Low", "Medium", "High", "Critical"]

        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)  # Add weight to the second column
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=0)
        
        self.create_controls()
        self.create_monitored_list()
        self.tag_selector = TagSelector(self)
        self.tag_selector.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.status_bar = ctk.CTkLabel(self, text="Prêt", anchor="w")
        self.status_bar.grid(row=2, column=0, columnspan=2, sticky="ew", padx=10, pady=5)

    def create_controls(self):
        control_frame = ctk.CTkFrame(self)
        control_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=5)
        url_frame = ctk.CTkFrame(control_frame)
        url_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(url_frame, text="URL:").pack(side="left")
        self.url_entry = ctk.CTkEntry(url_frame, width=400)
        self.url_entry.pack(side="left", padx=5)
        self.danger_combo = ctk.CTkComboBox(url_frame, values=self.danger_levels, width=120)
        self.danger_combo.pack(side="left", padx=5)
        self.danger_combo.set("Select Danger Level")
        self.load_btn = ctk.CTkButton(url_frame, text="Charger les Balises", command=self.load_tags_threaded)
        self.load_btn.pack(side="left", padx=5)
        self.add_btn = ctk.CTkButton(url_frame, text="Ajouter", command=self.add_url)
        self.add_btn.pack(side="left", padx=5)
        settings_frame = ctk.CTkFrame(control_frame)
        settings_frame.pack(fill="x", pady=5)
        ctk.CTkLabel(settings_frame, text="Intervalle (s):").pack(side="left")
        self.interval_entry = ctk.CTkEntry(settings_frame, width=80)
        self.interval_entry.insert(0, "30")
        self.interval_entry.pack(side="left", padx=5)
        ctk.CTkLabel(settings_frame, text="Durée (min):").pack(side="left", padx=10)
        self.duration_entry = ctk.CTkEntry(settings_frame, width=80)
        self.duration_entry.insert(0, "60")
        self.duration_entry.pack(side="left", padx=5)
        self.start_btn = ctk.CTkButton(control_frame, text="Démarrer la Surveillance", command=self.toggle_monitoring, fg_color="#2AAA8A", hover_color="#228B22")
        self.start_btn.pack(side="right", padx=5)

    def create_monitored_list(self):
        """Create the monitored sites list section."""
        # Create a frame for the monitored sites section
        self.monitored_list_frame = ctk.CTkFrame(self)
        self.monitored_list_frame.grid(row=0, column=1, rowspan=2, sticky="nsew", padx=10, pady=10)
        
        # Add a title
        ctk.CTkLabel(self.monitored_list_frame, text="Sites Surveillés", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Create a scrollable frame for the list
        self.monitored_list = ctk.CTkScrollableFrame(self.monitored_list_frame, width=400, height=600)
        self.monitored_list.pack(fill="both", expand=True, padx=5, pady=5)
        
        # Update the list with current URLs
        self.update_monitored_list()

    def update_monitored_list(self):
        """Updates the monitored sites list with monitoring status."""
        for widget in self.monitored_list.winfo_children():
            widget.destroy()
        for entry in self.monitored_urls:
            frame = ctk.CTkFrame(self.monitored_list)
            frame.pack(fill="x", pady=2, padx=5)
            frame.grid_columnconfigure(0, weight=1)
            
            color = self.get_danger_color(entry["danger_level"])
            
            # Create a label for the URL with fixed width and proper wrapping
            url = entry["url"]
            url_label = ctk.CTkLabel(frame, text=f"• {url}", anchor="w", text_color=color, 
                                    width=250, wraplength=250, justify="left")
            url_label.grid(row=0, column=0, sticky="w", padx=5)
            
            # Create a label for the danger level
            danger_label = ctk.CTkLabel(frame, text=entry["danger_level"], text_color=color, width=80)
            danger_label.grid(row=0, column=1, padx=5)
            
            # Add a button to choose output directory
            def choose_dir(u=url):
                try:
                    output_dir = filedialog.askdirectory(
                        title="Choisir le dossier de sauvegarde",
                        initialdir=os.getcwd()
                    )
                    if output_dir:
                        for site in self.monitored_urls:
                            if site["url"] == u:
                                site["output_dir"] = output_dir
                                self.update_status(f"Dossier de sauvegarde mis à jour pour {u}: {output_dir}")
                                break
                        save_monitored_urls(self.monitored_urls)
                except Exception as e:
                    self.update_status(f"Erreur lors de la sélection du dossier: {str(e)}")
            
            dir_btn = ctk.CTkButton(frame, text="📁", width=30, fg_color="#4169E1",
                                  command=choose_dir)
            dir_btn.grid(row=0, column=2, padx=2)
            
            # Add a button to start/stop monitoring
            is_monitoring = url in self.monitoring_threads and self.monitoring_threads[url][0].is_alive()
            
            if is_monitoring:
                btn = ctk.CTkButton(frame, text="Arrêter", width=70, fg_color="#FF4500",
                                   command=lambda u=url: self.stop_monitoring(u))
            else:
                btn = ctk.CTkButton(frame, text="Démarrer", width=70, fg_color="#2AAA8A",
                                   command=lambda u=url: self.start_monitoring(u))
            btn.grid(row=0, column=3, padx=2)
            
            # Add a remove button with a more visible style
            remove_btn = ctk.CTkButton(
                frame, 
                text="🗑️", 
                width=30, 
                fg_color="#FF0000",
                hover_color="#CC0000",
                command=lambda u=url: self.remove_url(u)
            )
            remove_btn.grid(row=0, column=4, padx=2)

    def get_danger_color(self, level):
        return {
            "Low": "#00FF00",
            "Medium": "#FFFF00",
            "High": "#FFA500",
            "Critical": "#FF0000"
        }.get(level, "#FFFFFF")

    def update_status(self, message):
        self.status_bar.configure(text=message)
        self.update_idletasks()

    def load_tags_threaded(self):
        url = self.url_entry.get().strip()
        if not url.startswith(('http://','https://')):
            messagebox.showerror("Erreur", "Format d'URL invalide")
            return
        self.current_url = url
        self.load_btn.configure(state="disabled", text="Chargement...")
        # Clear existing tags before loading new ones
        self.tag_selector.clear_tags()
        
        # Create and show loading screen
        self.loading_screen = LoadingScreen(self)
        self.loading_screen.update_progress(0, "Initialisation...")
        
        threading.Thread(target=self.load_tags, daemon=True).start()

    def load_tags(self):
        try:
            self.after(0, self.loading_screen.update_progress, 0.1, "Récupération du HTML...")
            html = fetch_html(self.current_url)
            soup = BeautifulSoup(html,'html.parser')
            self.tag_selector.clear_tags()
            
            total_tags = len(soup.find_all())
            for idx, tag in enumerate(soup.find_all()):
                self.after(0, self.tag_selector.add_tag, idx, tag.name, tag.attrs)
                if idx % 50 == 0:
                    progress = min(0.9, (idx / total_tags) * 0.9)  # Keep last 10% for completion
                    self.after(0, self.loading_screen.update_progress, progress, f"{idx} balises chargées...")
            
            # Restore previously selected tags if they exist
            entry = next((item for item in self.monitored_urls if item["url"] == self.current_url), None)
            if entry and "excluded_tags" in entry:
                for idx in entry["excluded_tags"]:
                    if idx < len(self.tag_selector.checkboxes):
                        self.tag_selector.checkboxes[idx].set(True)
            
            self.after(0, self.loading_screen.update_progress, 1.0, f"{total_tags} balises chargées")
            self.current_html = html
        except Exception as e:
            self.after(0, messagebox.showerror, "Erreur", str(e))
        finally:
            self.after(0, self.load_btn.configure, {"state":"normal","text":"Charger les Balises"})
            self.after(1000, self.loading_screen.destroy)  # Close loading screen after 1 second

    def add_url(self):
        url = self.url_entry.get().strip()
        danger_level = self.danger_combo.get()
        if not url.startswith(('http://','https://')):
            messagebox.showerror("Erreur URL","URL doit commencer par http:// ou https://")
            return
        if danger_level not in self.danger_levels:
            messagebox.showerror("Erreur Niveau Danger","Veuillez sélectionner un niveau de danger valide")
            return
        
        # Get selected tags before clearing
        selected_tags = self.tag_selector.get_selected_indices()
        
        existing = next((item for item in self.monitored_urls if item["url"] == url), None)
        if existing:
            existing["danger_level"] = danger_level
            existing["excluded_tags"] = selected_tags
        else:
            self.monitored_urls.append({
                "url": url, 
                "danger_level": danger_level,
                "excluded_tags": selected_tags
            })
        self.update_monitored_list()
        # Reset the tag selector and URL entry
        self.tag_selector.clear_tags()
        self.url_entry.delete(0, "end")
        self.danger_combo.set("Select Danger Level")
        self.load_btn.configure(state="normal", text="Charger les Balises")
        # Save the updated list to file
        save_monitored_urls(self.monitored_urls)
        messagebox.showinfo("Succès",f"Site ajouté avec niveau de danger: {danger_level}")

    def remove_url(self, url):
        """Remove a URL from the monitored list."""
        # Stop monitoring if it's active
        if url in self.monitoring_threads and self.monitoring_threads[url][0].is_alive():
            self.monitoring_threads[url][1].set()  # Set the stop event
            self.update_status(f"Surveillance arrêtée pour {url}")
        
        # Remove from the list
        self.monitored_urls = [item for item in self.monitored_urls if item["url"] != url]
        
        # Update the UI
        self.update_monitored_list()
        
        # Save the updated list to file
        save_monitored_urls(self.monitored_urls)
        
        # Show confirmation
        self.update_status(f"Site supprimé: {url}")

    def toggle_monitoring(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Erreur","Veuillez entrer une URL d'abord.")
            return
            
        # Check if this URL is already being monitored
        if url in self.monitoring_threads and self.monitoring_threads[url][0].is_alive():
            # Stop monitoring for this URL
            self.monitoring_threads[url][1].set()  # Set the stop event
            self.update_status(f"Surveillance arrêtée pour {url}")
            # Update the button text for this URL in the monitored list
            self.update_monitored_list()
        else:
            # Start monitoring for this URL
            entry = next((item for item in self.monitored_urls if item["url"] == url), None)
            if not entry:
                messagebox.showerror("Erreur","Veuillez ajouter le site à la liste de surveillance avec un niveau de danger")
                return
            self.current_danger_level = entry["danger_level"]
            try:
                interval = int(self.interval_entry.get())
                duration = int(self.duration_entry.get())
                if interval<=0 or duration<=0:
                    raise ValueError("Les valeurs doivent être positives")
            except Exception as e:
                messagebox.showerror("Erreur",f"Entrée invalide: {e}")
                return
                
            # Create a new stop event for this monitoring instance
            stop_event = threading.Event()
            
            # Create a new thread for this URL
            monitor_thread = threading.Thread(
                target=self.monitor_website, 
                args=(url, stop_event, interval, duration),
                daemon=True
            )
            
            # Store the thread and stop event
            self.monitoring_threads[url] = (monitor_thread, stop_event)
            
            # Start the thread
            monitor_thread.start()
            
            # Update the UI
            self.update_status(f"Surveillance démarrée pour {url} - Niveau Danger: {self.current_danger_level}")
            self.update_monitored_list()

    def check_site_status(self, url):
        """Check if a site is up and get its port."""
        try:
            # Parse the URL
            parsed_url = urlparse(url)
            hostname = parsed_url.netloc
            scheme = parsed_url.scheme
            
            # Default ports
            default_ports = {
                'http': 80,
                'https': 443
            }
            
            # Check if site is up
            response = requests.get(url, timeout=5)
            is_up = response.status_code < 400
            
            # Get the actual port being used
            actual_port = response.url.split(':')[-1].split('/')[0]
            if not actual_port.isdigit():
                actual_port = default_ports.get(scheme, 'unknown')
            
            return {
                'status': 'Up' if is_up else 'Down',
                'main_port': str(actual_port)
            }
        except Exception as e:
            return {
                'status': 'Down',
                'main_port': 'unknown'
            }

    def monitor_website(self, url, stop_event, interval, duration):
        """Monitor a specific website with its own parameters."""
        # Get the output directory from the monitored URLs
        entry = next((item for item in self.monitored_urls if item["url"] == url), None)
        if not entry or "output_dir" not in entry:
            self.after(0, messagebox.showerror, "Erreur", "Dossier de sauvegarde non défini")
            return
            
        # Create a subfolder with site name and timestamp
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        site_name = url.replace('://', '_').replace('/', '_')
        instance_id = f"{site_name}_{timestamp}"
        output_dir = os.path.join(entry["output_dir"], instance_id)
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            self.after(0, self.update_status, f"Dossier de sauvegarde pour {url}: {output_dir}")
        except Exception as e:
            self.after(0, messagebox.showerror, "Erreur Dossier", f"Création du dossier impossible: {e}")
            return
            
        try:
            # Get excluded tags
            excluded = self.tag_selector.get_selected_indices()
            
            # Fetch initial HTML
            self.after(0, self.update_status, f"Récupération du HTML initial depuis {url}...")
            base_html = fetch_html(url)
            base_html = modify_html(base_html, excluded)
            
            # Save initial snapshot
            initial_snap_file = os.path.join(output_dir, "initial_snapshot.html")
            with open(initial_snap_file, 'w', encoding='utf-8') as f:
                f.write(base_html)
            self.after(0, self.update_status, f"Snapshot initial sauvegardé pour {url}: initial_snapshot.html")
            
            # Start monitoring loop
            iteration = 0
            end_time = time.time() + duration * 60
            
            while time.time() < end_time and not stop_event.is_set():
                iteration += 1
                
                # Wait for the interval before taking the next snapshot
                self.after(0, self.update_status, f"Attente de {interval} secondes avant le prochain snapshot pour {url}...")
                for _ in range(interval):
                    if stop_event.is_set():
                        break
                    time.sleep(1)
                
                if stop_event.is_set():
                    break
                    
                try:
                    # Check site status
                    site_status = self.check_site_status(url)
                    status = site_status['status']
                    main_port = site_status['main_port']
                    
                    # Fetch current HTML
                    self.after(0, self.update_status, f"Récupération du HTML depuis {url}...")
                    cur_html = fetch_html(url)
                    mod_html = modify_html(cur_html, excluded)
                    
                    # Save snapshot
                    snap_file = os.path.join(output_dir, f"snapshot_{iteration}.html")
                    with open(snap_file, 'w', encoding='utf-8') as f:
                        f.write(mod_html)
                    self.after(0, self.update_status, f"Snapshot sauvegardé pour {url}: snapshot_{iteration}.html")
                    
                    # Generate diff
                    diff_path = os.path.join(output_dir, f"diff_{iteration}.txt")
                    has_changes = generate_diff(base_html, mod_html, diff_path)
                    
                    # Update status file with current state
                    status_file = os.path.join(output_dir, "status.txt")
                    current_time = time.strftime("%H:%M:%S")
                    
                    # Create status message with site status and changes
                    if has_changes:
                        status_message = f"Status: {status} | Port: {main_port} | Changements détectés à {current_time}"
                        base_html = mod_html  # Update base HTML for next comparison
                    else:
                        status_message = f"Status: {status} | Port: {main_port} | Pas de changements détectés à {current_time}"
                    
                    with open(status_file, 'w', encoding='utf-8') as f:
                        f.write(status_message)
                    
                except Exception as e:
                    self.after(0, self.update_status, f"Erreur pendant la surveillance de {url}: {str(e)}")
                    time.sleep(5)  # Wait a bit before retrying
            
            # Monitoring completed
            if url in self.monitoring_threads:
                del self.monitoring_threads[url]
            self.after(0, self.update_monitored_list)
            self.after(0, lambda: messagebox.showinfo("Terminé", f"Surveillance terminée pour {url}."))
            
        except Exception as e:
            if url in self.monitoring_threads:
                del self.monitoring_threads[url]
            self.after(0, self.update_monitored_list)
            self.after(0, messagebox.showerror, "Erreur Critique", f"Erreur pour {url}: {str(e)}")

    def start_monitoring(self, url):
        """Start monitoring a specific URL."""
        self.url_entry.delete(0, "end")
        self.url_entry.insert(0, url)
        self.toggle_monitoring()
    
    def stop_monitoring(self, url):
        """Stop monitoring a specific URL."""
        if url in self.monitoring_threads:
            self.monitoring_threads[url][1].set()  # Set the stop event
            self.update_status(f"Surveillance arrêtée pour {url}")
            self.update_monitored_list()

def get_monitored_sites():
    """Get the list of monitored sites with their danger levels."""
    return tasks_monitored_urls

def choose_output_directory():
    """Let the user choose where to save the monitoring folders."""
    root = ctk.CTk()
    root.withdraw()  # Hide the main window
    
    # Create a dialog to choose directory
    output_dir = filedialog.askdirectory(
        title="Choisir le dossier de sauvegarde",
        initialdir=os.getcwd()
    )
    
    root.destroy()
    return output_dir

def run_WebMontoring():
    """Run the Web Monitoring application."""
    root = ctk.CTk()
    root.title("Web Monitor")
    root.geometry("800x600")
    
    # Configure grid layout
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(0, weight=0)  # Title
    root.grid_rowconfigure(1, weight=0)  # URL input
    root.grid_rowconfigure(2, weight=0)  # Interval input
    root.grid_rowconfigure(3, weight=0)  # Danger level
    root.grid_rowconfigure(4, weight=0)  # Buttons
    root.grid_rowconfigure(5, weight=1)  # Status updates
    
    # Create title
    title_label = ctk.CTkLabel(root, text="Web Monitor", font=("Arial", 24, "bold"))
    title_label.grid(row=0, column=0, pady=20)
    
    # Create URL input frame
    url_frame = ctk.CTkFrame(root)
    url_frame.grid(row=1, column=0, padx=20, pady=10, sticky="ew")
    url_frame.grid_columnconfigure(1, weight=1)
    
    ctk.CTkLabel(url_frame, text="URL:").grid(row=0, column=0, padx=5)
    url_entry = ctk.CTkEntry(url_frame, placeholder_text="https://example.com")
    url_entry.grid(row=0, column=1, padx=5, sticky="ew")
    
    # Create interval input frame
    interval_frame = ctk.CTkFrame(root)
    interval_frame.grid(row=2, column=0, padx=20, pady=10, sticky="ew")
    interval_frame.grid_columnconfigure(1, weight=1)
    
    ctk.CTkLabel(interval_frame, text="Interval (minutes):").grid(row=0, column=0, padx=5)
    interval_entry = ctk.CTkEntry(interval_frame, placeholder_text="5")
    interval_entry.grid(row=0, column=1, padx=5, sticky="ew")
    
    # Create danger level frame
    danger_frame = ctk.CTkFrame(root)
    danger_frame.grid(row=3, column=0, padx=20, pady=10, sticky="ew")
    danger_frame.grid_columnconfigure(1, weight=1)
    
    ctk.CTkLabel(danger_frame, text="Niveau de danger:").grid(row=0, column=0, padx=5)
    danger_var = ctk.StringVar(value="Low")
    danger_combo = ctk.CTkComboBox(danger_frame, 
                                  values=["Low", "Medium", "High", "Critical"],
                                  variable=danger_var)
    danger_combo.grid(row=0, column=1, padx=5, sticky="ew")
    
    # Create button frame
    button_frame = ctk.CTkFrame(root)
    button_frame.grid(row=4, column=0, padx=20, pady=10, sticky="ew")
    button_frame.grid_columnconfigure(0, weight=1)
    button_frame.grid_columnconfigure(1, weight=1)
    
    # Create status updates frame
    status_frame = ctk.CTkFrame(root)
    status_frame.grid(row=5, column=0, padx=20, pady=10, sticky="nsew")
    status_frame.grid_columnconfigure(0, weight=1)
    status_frame.grid_rowconfigure(0, weight=1)
    
    status_text = ctk.CTkTextbox(status_frame, wrap="word")
    status_text.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    
    def add_status(message):
        """Add a status message to the text box."""
        status_text.insert("end", f"{message}\n")
        status_text.see("end")
    
    def start_monitoring():
        """Start monitoring the website."""
        url = url_entry.get().strip()
        interval = interval_entry.get().strip()
        danger_level = danger_var.get()
        
        if not url or not interval:
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")
            return
        
        try:
            interval = int(interval)
            if interval <= 0:
                raise ValueError("L'intervalle doit être positif")
        except ValueError:
            messagebox.showerror("Erreur", "L'intervalle doit être un nombre positif")
            return
        
        # Let user choose output directory
        output_dir = choose_output_directory()
        if not output_dir:  # User cancelled
            return
        
        # Add to monitored URLs
        tasks_monitored_urls.append({
            "url": url,
            "interval": interval,
            "danger_level": danger_level,
            "output_dir": output_dir
        })
        
        add_status(f"Surveillance démarrée pour {url}")
        add_status(f"Intervalle: {interval} minutes")
        add_status(f"Niveau de danger: {danger_level}")
        add_status(f"Dossier de sauvegarde: {output_dir}")
        
        # Clear inputs
        url_entry.delete(0, "end")
        interval_entry.delete(0, "end")
        danger_var.set("Low")
    
    def stop_monitoring():
        """Stop monitoring the website."""
        url = url_entry.get().strip()
        if not url:
            messagebox.showerror("Erreur", "Veuillez entrer l'URL à arrêter")
            return
        
        # Find and remove from monitored URLs
        for i, site in enumerate(tasks_monitored_urls):
            if site["url"] == url:
                tasks_monitored_urls.pop(i)
                add_status(f"Surveillance arrêtée pour {url}")
                break
        else:
            messagebox.showerror("Erreur", "URL non trouvée dans les sites surveillés")
    
    # Add buttons
    start_btn = ctk.CTkButton(button_frame, text="Démarrer", command=start_monitoring)
    start_btn.grid(row=0, column=0, padx=5, pady=5, sticky="ew")
    
    stop_btn = ctk.CTkButton(button_frame, text="Arrêter", command=stop_monitoring)
    stop_btn.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
    
    root.mainloop()

if __name__ == "__main__":
    app = WebMonitorApp()
    app.mainloop()