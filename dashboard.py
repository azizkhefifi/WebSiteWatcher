import customtkinter as ctk
import os
import time
import threading
from datetime import datetime
from tkinter import messagebox
import socket
import requests
from urllib.parse import urlparse
from bs4 import BeautifulSoup
import html2text

class DashboardApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Dashboard de Surveillance")
        self.geometry("800x800")
        
        # Store previous site statuses
        self.previous_site_statuses = {}
        
        # Store active monitoring sessions
        self.active_monitoring = set()
        
        # File lock for safe access
        self.file_lock = threading.Lock()
        
        # Store last status message for each site
        self.last_status_messages = {}
        
        # Store HTML changes for translation
        self.html_changes = {}
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Title row
        self.grid_rowconfigure(1, weight=1)  # Sites list row
        self.grid_rowconfigure(2, weight=0)  # Status updates row
        self.grid_rowconfigure(3, weight=0)  # Button row
        
        # Create title
        self.title_label = ctk.CTkLabel(self, text="Dashboard de Surveillance", font=("Arial", 20, "bold"))
        self.title_label.grid(row=0, column=0, pady=10)
        
        # Create monitored sites section
        self.create_monitored_sites_section()
        
        # Create status updates section
        self.create_status_updates_section()
        
        # Create button frame
        button_frame = ctk.CTkFrame(self)
        button_frame.grid(row=3, column=0, pady=10)
        
        # Add refresh button
        self.refresh_btn = ctk.CTkButton(button_frame, text="Actualiser", command=self.refresh_data)
        self.refresh_btn.pack(side="left", padx=10)
        
        # Add logout button
        self.logout_btn = ctk.CTkButton(button_frame, text="Déconnexion", 
                                      command=self.logout, fg_color="#FF5733")
        self.logout_btn.pack(side="left", padx=10)
        
        # Start auto-refresh thread
        self.stop_refresh = threading.Event()
        self.refresh_thread = threading.Thread(target=self.auto_refresh, daemon=True)
        self.refresh_thread.start()
        
        # Initial data load
        self.refresh_data()
    
    def logout(self):
        """Log out and return to login page"""
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment vous déconnecter?"):
            self.stop_refresh.set()  # Stop the refresh thread
            self.destroy()  # Close the dashboard
            
            # Import here to avoid circular imports
            from admin import LoginPage
            app = LoginPage()  # Open the login page
            app.mainloop()
            
    def create_monitored_sites_section(self):
        # Create frame for monitored sites
        self.sites_frame = ctk.CTkFrame(self)
        self.sites_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure grid for sites frame
        self.sites_frame.grid_columnconfigure(0, weight=1)
        self.sites_frame.grid_rowconfigure(1, weight=1)
        
        # Add title
        ctk.CTkLabel(self.sites_frame, text="Sites Surveillés", font=("Arial", 16, "bold")).grid(row=0, column=0, pady=5)
        
        # Create scrollable frame for sites
        self.sites_list = ctk.CTkScrollableFrame(self.sites_frame, height=300)
        self.sites_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    def create_status_updates_section(self):
        # Create frame for status updates
        self.status_frame = ctk.CTkFrame(self)
        self.status_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        
        # Configure grid for status frame
        self.status_frame.grid_columnconfigure(0, weight=1)
        self.status_frame.grid_rowconfigure(1, weight=1)
        
        # Add title
        ctk.CTkLabel(self.status_frame, text="Mises à jour de Statut", font=("Arial", 16, "bold")).grid(row=0, column=0, pady=5)
        
        # Create scrollable frame for status updates
        self.status_list = ctk.CTkScrollableFrame(self.status_frame, height=150)
        self.status_list.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    def check_site_status(self, url):
        """Check if a site is up and get its port with detailed error reporting."""
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
            
            # Try to establish connection first
            try:
                # Check if we can resolve the hostname
                socket.gethostbyname(hostname)
            except socket.gaierror:
                return {
                    'status': 'Down',
                    'main_port': 'unknown',
                    'error': 'DNS Resolution Failed'
                }
            
            # Check if site is up with detailed error handling
            try:
                start_time = time.time()
                response = requests.get(url, timeout=5)
                response_time = time.time() - start_time
                
                # Check response time
                if response_time > 3:
                    return {
                        'status': 'Slow',
                        'main_port': str(default_ports.get(scheme, 'unknown')),
                        'error': f'Response Time: {response_time:.2f}s'
                    }
                
                # Check status code
                if response.status_code >= 500:
                    return {
                        'status': 'Down',
                        'main_port': str(default_ports.get(scheme, 'unknown')),
                        'error': f'Server Error ({response.status_code})'
                    }
                elif response.status_code >= 400:
                    return {
                        'status': 'Down',
                        'main_port': str(default_ports.get(scheme, 'unknown')),
                        'error': f'Client Error ({response.status_code})'
                    }
                elif response.status_code >= 300:
                    return {
                        'status': 'Up',
                        'main_port': str(default_ports.get(scheme, 'unknown')),
                        'error': f'Redirect ({response.status_code})'
                    }
                
                # Check if we got actual content
                if len(response.text.strip()) < 100:
                    return {
                        'status': 'Warning',
                        'main_port': str(default_ports.get(scheme, 'unknown')),
                        'error': 'Minimal Content'
                    }
                
                # Get the actual port being used
                actual_port = response.url.split(':')[-1].split('/')[0]
                if not actual_port.isdigit():
                    actual_port = default_ports.get(scheme, 'unknown')
                
                return {
                    'status': 'Up',
                    'main_port': str(actual_port),
                    'error': None
                }
                
            except requests.exceptions.Timeout:
                return {
                    'status': 'Down',
                    'main_port': str(default_ports.get(scheme, 'unknown')),
                    'error': 'Connection Timeout'
                }
            except requests.exceptions.ConnectionError:
                return {
                    'status': 'Down',
                    'main_port': str(default_ports.get(scheme, 'unknown')),
                    'error': 'Connection Failed'
                }
            except requests.exceptions.SSLError:
                return {
                    'status': 'Down',
                    'main_port': str(default_ports.get(scheme, 'unknown')),
                    'error': 'SSL Error'
                }
            except Exception as e:
                return {
                    'status': 'Down',
                    'main_port': str(default_ports.get(scheme, 'unknown')),
                    'error': f'Request Error: {str(e)}'
                }
                
        except Exception as e:
            return {
                'status': 'Down',
                'main_port': 'unknown',
                'error': f'General Error: {str(e)}'
            }

    def translate_html_to_text(self, html_content):
        """Convert HTML to plain English text."""
        try:
            # Create HTML to text converter
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = False
            h.ignore_tables = False
            h.body_width = 0  # No wrapping
            
            # Convert HTML to text
            text = h.handle(html_content)
            
            # Clean up the text
            text = text.replace('\\', '')  # Remove escape characters
            text = text.replace('*', '')   # Remove markdown emphasis
            text = text.strip()            # Remove extra whitespace
            
            return text
        except Exception as e:
            return f"Error translating HTML: {str(e)}"

    def format_diff_content(self, diff_content):
        """Format the diff content to make it more readable."""
        try:
            # Split the content into lines
            lines = diff_content.split('\n')
            formatted_lines = []
            
            for line in lines:
                if line.startswith('+'):
                    # Added content (green)
                    formatted_lines.append(f"Added: {line[1:].strip()}")
                elif line.startswith('-'):
                    # Removed content (red)
                    formatted_lines.append(f"Removed: {line[1:].strip()}")
                elif line.startswith('@'):
                    # Section header
                    formatted_lines.append(f"\n--- Change Location ---")
                elif line.startswith(' '):
                    # Unchanged content
                    formatted_lines.append(f"Context: {line.strip()}")
                else:
                    # Other content
                    formatted_lines.append(line)
            
            # Join the lines with proper spacing
            formatted_content = '\n'.join(formatted_lines)
            
            # Add a summary at the top
            added_count = sum(1 for line in lines if line.startswith('+'))
            removed_count = sum(1 for line in lines if line.startswith('-'))
            summary = f"""Summary of Changes:
- {added_count} lines added
- {removed_count} lines removed

Detailed Changes:
----------------
"""
            return summary + formatted_content
            
        except Exception as e:
            print(f"Error formatting diff content: {e}")
            return diff_content

    def show_translation_window(self, html_content, url):
        """Show a window with the translated diff content in a readable way."""
        print(f"Showing translation window for URL: {url}")
        try:
            # Create a new window
            translation_window = ctk.CTkToplevel(self)
            translation_window.title(f"Changes Detected - {url}")
            translation_window.geometry("1000x700")
            
            # Create a scrollable frame
            scroll_frame = ctk.CTkScrollableFrame(translation_window)
            scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Add title
            title_label = ctk.CTkLabel(scroll_frame, text="Changes Detected", font=("Arial", 16, "bold"))
            title_label.pack(pady=5)
            
            # Add URL
            url_label = ctk.CTkLabel(scroll_frame, text=f"URL: {url}", font=("Arial", 12))
            url_label.pack(pady=5)
            
            # Format the diff content
            formatted_content = self.format_diff_content(html_content)
            
            # Create a text widget for better text display (no color coding)
            text_widget = ctk.CTkTextbox(scroll_frame, width=950, height=500)
            text_widget.pack(pady=5, padx=5, fill="both", expand=True)
            text_widget.insert("1.0", formatted_content)
            text_widget.configure(state="disabled")  # Make read-only
            
            # Add explanation
            explanation_frame = ctk.CTkFrame(scroll_frame)
            explanation_frame.pack(fill="x", pady=10, padx=5)
            
            explanation_text = """
How to read the changes:
- Lines starting with 'Added:' show new content that was added
- Lines starting with 'Removed:' show content that was removed
- '--- Change Location ---' shows where in the page the changes occurred
- 'Context:' lines show the surrounding context
"""
            explanation_label = ctk.CTkLabel(explanation_frame, text=explanation_text,
                                          justify="left", wraplength=900)
            explanation_label.pack(pady=5, padx=5)
            
            # Add close button
            close_btn = ctk.CTkButton(translation_window, text="Close", 
                                    command=translation_window.destroy)
            close_btn.pack(pady=10)
            
            print("Translation window created successfully")
            
        except Exception as e:
            print(f"Error in show_translation_window: {str(e)}")
            messagebox.showerror("Error", f"Failed to show changes: {str(e)}")

    def add_status_update(self, message, html_content=None, url=None):
        """Add a status update to the status list with clickable translation."""
        print(f"Adding status update: {message}")  # Debug print
        print(f"HTML content available: {html_content is not None}")  # Debug print
        
        frame = ctk.CTkFrame(self.status_list)
        frame.pack(fill="x", pady=2)
        
        # Add timestamp
        timestamp = datetime.now().strftime("%H:%M:%S")
        ctk.CTkLabel(frame, text=f"[{timestamp}]", anchor="w", width=80).pack(side="left", padx=5)
        
        # Create a clickable label for the message
        message_label = ctk.CTkLabel(frame, text=message, anchor="w", 
                                   wraplength=350, justify="left",
                                   cursor="hand2")  # Show hand cursor on hover
        
        # Store HTML content if provided
        if html_content and url:
            print(f"Storing HTML content for message: {message[:50]}...")  # Debug print
            self.html_changes[message] = (html_content, url)
            message_label.configure(cursor="hand2")
            
            # Create a function to handle the click event
            def on_click(event, msg=message):
                print(f"Click detected on message: {msg[:50]}...")  # Debug print
                if msg in self.html_changes:
                    print("Found HTML content in storage")  # Debug print
                    html, site_url = self.html_changes[msg]
                    self.show_translation_window(html, site_url)
                else:
                    print("No HTML content found in storage")  # Debug print
            
            # Bind the click event
            message_label.bind("<Button-1>", on_click)
            print("Click event bound to label")  # Debug print
        
        message_label.pack(side="left", fill="x", expand=True, padx=5)

    def get_monitored_sites(self):
        """Get the list of monitored sites with their status."""
        from task1_review import tasks_monitored_urls
        monitored_sites = []
        
        with self.file_lock:
            for site in tasks_monitored_urls:
                url = site["url"]
                danger_level = site["danger_level"]
                base_dir = os.path.join(os.getcwd(), "WebMonitor_Output")
                
                # Default values
                status = "Up"
                main_port = "unknown"
                error = None
                last_modified = time.time()
                is_monitoring = False
                
                try:
                    # Check site status every 60 seconds
                    current_time = time.time()
                    if not hasattr(self, 'last_status_check') or url not in self.last_status_check or \
                       current_time - self.last_status_check[url] >= 60:
                        site_status = self.check_site_status(url)
                        status = site_status['status']
                        main_port = site_status['main_port']
                        error = site_status.get('error')
                        
                        # Update last check time
                        if not hasattr(self, 'last_status_check'):
                            self.last_status_check = {}
                        self.last_status_check[url] = current_time
                    
                    # Find the most recent monitoring directory for this site
                    site_dirs = [d for d in os.listdir(base_dir) 
                               if d.startswith(url.replace('://', '_').replace('/', '_'))]
                    if site_dirs:
                        latest_dir = max(site_dirs)
                        output_dir = os.path.join(base_dir, latest_dir)
                        
                        # Check if monitoring is active
                        for file in os.listdir(output_dir):
                            file_path = os.path.join(output_dir, file)
                            if os.path.getmtime(file_path) > current_time - 60:
                                is_monitoring = True
                                break
                        
                        # Check for status file
                        status_file = os.path.join(output_dir, "status.txt")
                        
                        if os.path.exists(status_file):
                            if os.path.getmtime(status_file) > current_time - 60:
                                with open(status_file, 'r', encoding='utf-8') as f:
                                    status_message = f.read()
                                    
                                    # Check for changes
                                    if "changements détectés" in status_message.lower():
                                        current_message = f"{status_message} - {url} (Niveau: {danger_level})"
                                        
                                        # Read diff files if available
                                        html_content = None
                                        diff_files = [f for f in os.listdir(output_dir) if f.startswith("diff_") and f.endswith(".txt")]
                                        if diff_files:
                                            try:
                                                # Get the most recent diff file
                                                latest_diff = max(diff_files)
                                                diff_file_path = os.path.join(output_dir, latest_diff)
                                                with open(diff_file_path, 'r', encoding='utf-8') as cf:
                                                    html_content = cf.read()
                                                    print(f"Successfully read diff content for {url} from {latest_diff}")
                                                    print(f"Diff content length: {len(html_content)}")
                                            except Exception as e:
                                                print(f"Error reading diff file for {url}: {e}")
                                        
                                        if url not in self.last_status_messages or self.last_status_messages[url] != current_message:
                                            print(f"Adding new status update for {url}")
                                            self.add_status_update(current_message, html_content, url)
                                            self.last_status_messages[url] = current_message
                except Exception as e:
                    print(f"Error checking site {url}: {e}")
                    continue
                
                monitored_sites.append({
                    "url": url,
                    "status": status,
                    "danger_level": danger_level,
                    "last_updated": last_modified,
                    "is_monitoring": is_monitoring,
                    "main_port": main_port,
                    "error": error
                })
        
        return monitored_sites
    
    def get_danger_color(self, level):
        """Get the color for a danger level."""
        return {
            "Low": "#00FF00",      # Green
            "Medium": "#FFA500",    # Orange
            "High": "#FF4500",      # Red-Orange
            "Critical": "#FF0000"   # Red
        }.get(level, "#FFFFFF")     # White as default
    
    def update_monitored_sites(self):
        """Update the monitored sites list in the UI."""
        # Clear existing items
        for widget in self.sites_list.winfo_children():
            widget.destroy()
        
        # Get monitored sites
        sites = self.get_monitored_sites()
        
        if not sites:
            ctk.CTkLabel(self.sites_list, text="Aucun site surveillé").pack(pady=10)
            return
        
        # Add each site to the list
        for site in sites:
            url = site['url']
            current_status = site['status']
            is_monitoring = site['is_monitoring']
            main_port = site['main_port']
            error = site.get('error', None)
            
            # Update active monitoring set
            if is_monitoring:
                self.active_monitoring.add(url)
            else:
                self.active_monitoring.discard(url)
            
            frame = ctk.CTkFrame(self.sites_list)
            frame.pack(fill="x", pady=2)
            
            # Create a sub-frame for URL and danger level
            url_frame = ctk.CTkFrame(frame)
            url_frame.pack(side="left", fill="x", expand=True, padx=5)
            
            # URL label
            url_label = ctk.CTkLabel(url_frame, text=f"• {url}", anchor="w", 
                                   width=300, wraplength=300, justify="left")
            url_label.pack(side="left", fill="x", expand=True)
            
            # Danger level label with color
            danger_color = self.get_danger_color(site["danger_level"])
            danger_label = ctk.CTkLabel(url_frame, text=site["danger_level"], 
                                      text_color=danger_color, width=80)
            danger_label.pack(side="right", padx=5)
            
            # Status label with color
            status_colors = {
                'Up': "#00FF00",      # Green
                'Down': "#FF0000",    # Red
                'Slow': "#FFA500",    # Orange
                'Warning': "#FFFF00"  # Yellow
            }
            status_color = status_colors.get(current_status, "#808080")
            status_text = f"Status: {current_status}"
            if error:
                status_text += f" ({error})"
            status_label = ctk.CTkLabel(frame, text=status_text, 
                                      text_color=status_color, width=200)
            status_label.pack(side="right", padx=5)
            
            # Add monitoring status indicator
            monitor_color = "#00FF00" if is_monitoring else "#808080"
            monitor_text = "En cours" if is_monitoring else "Arrêté"
            monitor_label = ctk.CTkLabel(frame, text=monitor_text, 
                                       text_color=monitor_color, width=80)
            monitor_label.pack(side="right", padx=5)
            
            # Add port information
            port_label = ctk.CTkLabel(frame, text=f"Port: {main_port}", width=80)
            port_label.pack(side="right", padx=5)
            
            # Add last updated time
            last_updated = datetime.fromtimestamp(site["last_updated"]).strftime("%H:%M:%S")
            time_label = ctk.CTkLabel(frame, text=f"Dernière mise à jour: {last_updated}", 
                                    width=150)
            time_label.pack(side="right", padx=5)
    
    def refresh_data(self):
        """Refresh the monitored sites."""
        self.update_monitored_sites()
        # Note: Removed the generic "Données actualisées" message
        # Status updates will now only show when changes are detected
    
    def auto_refresh(self):
        """Auto-refresh the data every 60 seconds."""
        while not self.stop_refresh.is_set():
            time.sleep(60)  # Check every 60 seconds
            self.after(0, self.refresh_data)
    
    def on_closing(self):
        """Handle window closing."""
        self.stop_refresh.set()
        self.destroy()

def run_dashboard():
    """Run the dashboard application."""
    app = DashboardApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()

if __name__ == "__main__":
    run_dashboard()
