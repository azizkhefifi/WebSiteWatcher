import customtkinter as ctk
from tkinter import messagebox
import sqlite3
import hashlib
import os
from task1_review import run_WebMontoring
from dashboard import run_dashboard
import threading

class LoginPage(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Login")
        self.geometry("400x300")
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        
        # Create title
        self.title_label = ctk.CTkLabel(self, text="Login", font=("Arial", 24, "bold"))
        self.title_label.grid(row=0, column=0, pady=20)
        
        # Create login frame
        login_frame = ctk.CTkFrame(self)
        login_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Username entry
        self.username_entry = ctk.CTkEntry(login_frame, placeholder_text="Nom d'utilisateur")
        self.username_entry.pack(pady=10, padx=20, fill="x")
        
        # Password entry
        self.password_entry = ctk.CTkEntry(login_frame, placeholder_text="Mot de passe", show="*")
        self.password_entry.pack(pady=10, padx=20, fill="x")
        
        # Login button
        self.login_btn = ctk.CTkButton(login_frame, text="Se connecter", command=self.login)
        self.login_btn.pack(pady=20)
        
        # Initialize database and ensure default users exist
        create_users_table()
        self.ensure_default_users()
    
    def ensure_default_users(self):
        """Ensures default users exist without showing messages."""
        try:
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            
            # Check if users exist
            c.execute('SELECT COUNT(*) FROM users')
            count = c.fetchone()[0]
            
            if count == 0:
                # Admin user
                admin_pwd = 'admin'
                admin_hash = hashlib.sha256(admin_pwd.encode()).hexdigest()
                c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                        ('admin', admin_hash, 'admin'))
                
                # Regular user
                user_pwd = 'user'
                user_hash = hashlib.sha256(user_pwd.encode()).hexdigest()
                c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                        ('user', user_hash, 'user'))
                
                conn.commit()
            
            conn.close()
        except Exception as e:
            print(f"Error ensuring default users: {e}")
    
    def reset_database(self):
        """Reset the database and create default users."""
        try:
            # Close any open connections
            conn = sqlite3.connect('users.db')
            conn.close()
            
            # Delete existing database
            if os.path.exists('users.db'):
                os.remove('users.db')
                print("Deleted existing database")
            
            # Create fresh database
            create_users_table()
            
            # Create default users with plaintext passwords
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            
            # Admin user
            admin_pwd = 'admin'
            admin_hash = hashlib.sha256(admin_pwd.encode()).hexdigest()
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                    ('admin', admin_hash, 'admin'))
            
            # Regular user
            user_pwd = 'user'
            user_hash = hashlib.sha256(user_pwd.encode()).hexdigest()
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                    ('user', user_hash, 'user'))
            
            conn.commit()
            
            # Verify users
            c.execute('SELECT username, password, role FROM users')
            users = c.fetchall()
            print("Recreated database with users:")
            for user in users:
                print(f"  Username: {user[0]}, Password hash: {user[1][:10]}..., Role: {user[2]}")
            
            conn.close()
        except Exception as e:
            print(f"Error resetting database: {e}")
    
    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        
        if not username or not password:
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")
            return
        
        print(f"Login attempt: Username={username}, Password={password}")
        
        # Hash the password
        hashed_password = hashlib.sha256(password.encode()).hexdigest()
        print(f"Hashed password: {hashed_password}")
        
        try:
            # Check credentials
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            
            # Debug: First check if the user exists
            c.execute('SELECT username FROM users WHERE username = ?', (username,))
            user_exists = c.fetchone()
            if not user_exists:
                print(f"User '{username}' does not exist in database")
            else:
                print(f"User '{username}' found in database")
                
                # Debug: Check all users and passwords
                c.execute('SELECT username, password, role FROM users')
                all_users = c.fetchall()
                print(f"All users in database:")
                for user in all_users:
                    print(f"  Username: {user[0]}, Password hash: {user[1][:10]}..., Role: {user[2]}")
            
            # Actual login query
            c.execute('SELECT role FROM users WHERE username = ? AND password = ?',
                     (username, hashed_password))
            result = c.fetchone()
            
            if result:
                print(f"Login successful, role: {result[0]}")
            else:
                print("Login failed: invalid credentials")
                
                # Try without hashing (for debugging)
                c.execute('SELECT role FROM users WHERE username = ?', (username,))
                user = c.fetchone()
                if user:
                    print(f"User exists but password doesn't match")
                
            conn.close()
            
            # Continue with normal login flow
            if result:
                role = result[0]
                messagebox.showinfo("Succès", f"Bienvenue, {username}!")
                self.destroy()  # Close login window
                
                if role == 'admin':
                    # Open admin panel
                    app = AdminPanel()
                    app.mainloop()
                else:
                    # Open dashboard for regular users
                    run_dashboard()
            else:
                messagebox.showerror("Erreur", "Nom d'utilisateur ou mot de passe incorrect")
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur de connexion: {str(e)}")
            print(f"Login error: {e}")

class AdminPanel(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Admin Panel")
        self.geometry("800x600")
        
        # Configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # Create title
        self.title_label = ctk.CTkLabel(self, text="Admin Panel", font=("Arial", 24, "bold"))
        self.title_label.grid(row=0, column=0, columnspan=2, pady=20)
        
        # Create user management section
        self.create_user_management_section()
        
        # Create windows access section
        self.create_windows_section()
        
        # Add logout button at the bottom
        self.logout_btn = ctk.CTkButton(self, text="Déconnexion", 
                                      command=self.logout, fg_color="#FF5733")
        self.logout_btn.grid(row=2, column=0, columnspan=2, pady=20)
    
    def logout(self):
        """Log out and return to login page"""
        if messagebox.askyesno("Confirmation", "Voulez-vous vraiment vous déconnecter?"):
            self.destroy()  # Close the admin panel
            app = LoginPage()  # Open the login page
            app.mainloop()
    
    def create_user_management_section(self):
        # User Management Frame
        user_frame = ctk.CTkFrame(self)
        user_frame.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        
        # Title
        ctk.CTkLabel(user_frame, text="Gestion des Utilisateurs", 
                    font=("Arial", 18, "bold")).pack(pady=10)
        
        # Username entry
        self.username_entry = ctk.CTkEntry(user_frame, placeholder_text="Nom d'utilisateur")
        self.username_entry.pack(pady=5, padx=20, fill="x")
        
        # Password entry
        self.password_entry = ctk.CTkEntry(user_frame, placeholder_text="Mot de passe", show="*")
        self.password_entry.pack(pady=5, padx=20, fill="x")
        
        # Role selection
        self.role_var = ctk.StringVar(value="user")
        role_frame = ctk.CTkFrame(user_frame)
        role_frame.pack(pady=5, fill="x")
        ctk.CTkRadioButton(role_frame, text="User", variable=self.role_var, 
                          value="user").pack(side="left", padx=20)
        ctk.CTkRadioButton(role_frame, text="Admin", variable=self.role_var, 
                          value="admin").pack(side="left", padx=20)
        
        # Add user button
        ctk.CTkButton(user_frame, text="Ajouter Utilisateur", 
                     command=self.add_user).pack(pady=10)
        
        # Users list
        ctk.CTkLabel(user_frame, text="Liste des Utilisateurs", 
                    font=("Arial", 16)).pack(pady=5)
        self.users_list = ctk.CTkScrollableFrame(user_frame, height=200)
        self.users_list.pack(pady=5, padx=20, fill="x")
        
        # Refresh users list button
        ctk.CTkButton(user_frame, text="Actualiser la Liste", 
                     command=self.refresh_users_list).pack(pady=5)
        
        # Initial users list load
        self.refresh_users_list()
        
    def create_windows_section(self):
        # Windows Access Frame
        windows_frame = ctk.CTkFrame(self)
        windows_frame.grid(row=1, column=1, padx=20, pady=10, sticky="nsew")
        
        # Title
        ctk.CTkLabel(windows_frame, text="Accès aux Fenêtres", 
                    font=("Arial", 18, "bold")).pack(pady=10)
        
        # WebMonitor button
        ctk.CTkButton(windows_frame, text="Ouvrir WebMonitor", 
                     command=self.open_webmonitor).pack(pady=10, padx=20, fill="x")
        
        # Dashboard button
        ctk.CTkButton(windows_frame, text="Ouvrir Dashboard", 
                     command=self.open_dashboard).pack(pady=10, padx=20, fill="x")
    
    def add_user(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()
        role = self.role_var.get()
        
        if not username or not password:
            messagebox.showerror("Erreur", "Veuillez remplir tous les champs")
            return
        
        try:
            # Hash the password
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            
            # Add user to database
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('INSERT INTO users (username, password, role) VALUES (?, ?, ?)',
                     (username, hashed_password, role))
            conn.commit()
            conn.close()
            
            messagebox.showinfo("Succès", "Utilisateur ajouté avec succès")
            
            # Clear entries
            self.username_entry.delete(0, 'end')
            self.password_entry.delete(0, 'end')
            self.role_var.set("user")
            
            # Refresh users list
            self.refresh_users_list()
            
        except sqlite3.IntegrityError:
            messagebox.showerror("Erreur", "Ce nom d'utilisateur existe déjà")
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de l'ajout: {str(e)}")
    
    def refresh_users_list(self):
        # Clear current list
        for widget in self.users_list.winfo_children():
            widget.destroy()
        
        try:
            # Get users from database
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute('SELECT username, role FROM users')
            users = c.fetchall()
            conn.close()
            
            # Add users to list
            for username, role in users:
                frame = ctk.CTkFrame(self.users_list)
                frame.pack(fill="x", pady=2, padx=5)
                
                ctk.CTkLabel(frame, text=username, width=120).pack(side="left", padx=5)
                ctk.CTkLabel(frame, text=role, width=80).pack(side="left", padx=5)
                
                # Add delete button
                ctk.CTkButton(frame, text="Supprimer", width=80,
                            command=lambda u=username: self.delete_user(u)).pack(side="right", padx=5)
                
        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors du chargement: {str(e)}")
    
    def delete_user(self, username):
        if messagebox.askyesno("Confirmation", f"Voulez-vous vraiment supprimer {username}?"):
            try:
                conn = sqlite3.connect('users.db')
                c = conn.cursor()
                c.execute('DELETE FROM users WHERE username = ?', (username,))
                conn.commit()
                conn.close()
                
                messagebox.showinfo("Succès", "Utilisateur supprimé avec succès")
                self.refresh_users_list()
                
            except Exception as e:
                messagebox.showerror("Erreur", f"Erreur lors de la suppression: {str(e)}")
    
    def open_webmonitor(self):
        from task1_review import WebMonitorApp
        # Create a new thread for the WebMonitor
        monitor_thread = threading.Thread(target=lambda: WebMonitorApp().mainloop(), daemon=True)
        monitor_thread.start()
    
    def open_dashboard(self):
        from dashboard import run_dashboard
        # Create a new thread for the Dashboard
        dashboard_thread = threading.Thread(target=run_dashboard, daemon=True)
        dashboard_thread.start()

def create_users_table():
    """Creates the users table if it doesn't already exist."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'user'))
        )
    ''')
    conn.commit()
    conn.close()

if __name__ == "__main__":
    app = LoginPage()
    app.mainloop()
