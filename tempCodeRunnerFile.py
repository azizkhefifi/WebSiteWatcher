        # Add title
        ctk.CTkLabel(self.status_frame, text="Mises à jour de Statut", font=("Arial", 16, "bold")).pack(pady=5)
        
        # Create scrollable frame for status updates
        self.status_list = ctk.CTkScrollableFrame(self.status_frame, height=150)
        self.status_list.pack(fill="both", expand=True, padx=5, pady=5)
    
    def get_monitored_sites(self):
        """Get the list of monitored sites from the WebMonitor_Output directory."""
        monitored_sites = []
 