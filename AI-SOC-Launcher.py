#!/usr/bin/env python3
"""
AI-SOC Graphical Launcher
==========================
Simplified graphical interface for the AI Security Operations Center platform

Usage:
    Execute this file via double-click to launch the AI-SOC control interface
    OR
    python AI-SOC-Launcher.py
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import os
import sys
import time
import webbrowser
from pathlib import Path

class AISOCLauncher:
    def __init__(self, root):
        self.root = root
        self.root.title("AI-SOC Control Center")
        self.root.geometry("900x700")
        self.root.resizable(True, True)

        # Get script directory
        self.base_dir = Path(__file__).parent.absolute()
        os.chdir(self.base_dir)

        # State tracking
        self.is_running = False
        self.services_status = {}

        # Setup UI
        self.setup_ui()

        # Check prerequisites
        self.root.after(500, self.check_prerequisites)

    def setup_ui(self):
        """Create the user interface"""
        # Header
        header_frame = tk.Frame(self.root, bg="#2c3e50", height=100)
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        header_frame.pack_propagate(False)

        title = tk.Label(
            header_frame,
            text="🛡️ AI Security Operations Center",
            font=("Arial", 24, "bold"),
            bg="#2c3e50",
            fg="white"
        )
        title.pack(pady=25)

        # Main content area
        content_frame = tk.Frame(self.root, bg="#ecf0f1")
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Status Panel
        status_panel = tk.LabelFrame(
            content_frame,
            text="System Status",
            font=("Arial", 12, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        status_panel.pack(fill=tk.X, padx=5, pady=5)

        self.status_label = tk.Label(
            status_panel,
            text="⚪ System Not Started",
            font=("Arial", 14),
            bg="#ecf0f1",
            fg="#7f8c8d"
        )
        self.status_label.pack(pady=5)

        self.progress = ttk.Progressbar(
            status_panel,
            mode='indeterminate',
            length=400
        )
        self.progress.pack(pady=10)

        # Control Buttons
        button_frame = tk.Frame(content_frame, bg="#ecf0f1")
        button_frame.pack(fill=tk.X, padx=5, pady=10)

        self.start_button = tk.Button(
            button_frame,
            text="▶ START AI-SOC",
            command=self.start_system,
            bg="#27ae60",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=30,
            pady=15,
            relief=tk.RAISED,
            cursor="hand2"
        )
        self.start_button.pack(side=tk.LEFT, padx=10)

        self.stop_button = tk.Button(
            button_frame,
            text="⏹ STOP AI-SOC",
            command=self.stop_system,
            bg="#e74c3c",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=30,
            pady=15,
            relief=tk.RAISED,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.stop_button.pack(side=tk.LEFT, padx=10)

        self.dashboard_button = tk.Button(
            button_frame,
            text="🌐 Open Dashboard",
            command=self.open_dashboard,
            bg="#3498db",
            fg="white",
            font=("Arial", 14, "bold"),
            padx=30,
            pady=15,
            relief=tk.RAISED,
            state=tk.DISABLED,
            cursor="hand2"
        )
        self.dashboard_button.pack(side=tk.LEFT, padx=10)

        # Services Status
        services_frame = tk.LabelFrame(
            content_frame,
            text="Services Status",
            font=("Arial", 11, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        services_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.services_text = scrolledtext.ScrolledText(
            services_frame,
            height=8,
            font=("Consolas", 10),
            bg="white",
            fg="#2c3e50",
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.services_text.pack(fill=tk.BOTH, expand=True)
        self.services_text.insert(tk.END, "Click START to launch AI-SOC services...\n")
        self.services_text.config(state=tk.DISABLED)

        # Log Output
        log_frame = tk.LabelFrame(
            content_frame,
            text="System Log",
            font=("Arial", 11, "bold"),
            bg="#ecf0f1",
            padx=10,
            pady=10
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            height=10,
            font=("Consolas", 9),
            bg="#1e1e1e",
            fg="#00ff00",
            relief=tk.SUNKEN,
            borderwidth=2
        )
        self.log_text.pack(fill=tk.BOTH, expand=True)
        self.log_text.insert(tk.END, "AI-SOC Launcher initialized.\n")
        self.log_text.config(state=tk.DISABLED)

        # Footer
        footer = tk.Label(
            self.root,
            text="AI-SOC v1.0 | AI-Augmented Security Operations Center",
            bg="#34495e",
            fg="white",
            font=("Arial", 9),
            pady=5
        )
        footer.pack(fill=tk.X, side=tk.BOTTOM)

    def log(self, message, color=None):
        """Add message to log"""
        self.log_text.config(state=tk.NORMAL)
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.log_text.config(state=tk.DISABLED)

    def update_services(self, message):
        """Update services status display"""
        self.services_text.config(state=tk.NORMAL)
        self.services_text.insert(tk.END, f"{message}\n")
        self.services_text.see(tk.END)
        self.services_text.config(state=tk.DISABLED)

    def check_prerequisites(self):
        """Check if Docker is installed and running"""
        self.log("Checking system requirements...")

        # Check Docker
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.log("✓ Docker is installed")
                self.check_docker_running()
            else:
                self.show_docker_not_installed()
        except FileNotFoundError:
            self.show_docker_not_installed()
        except Exception as e:
            self.log(f"✗ Error checking Docker: {e}")

    def check_docker_running(self):
        """Check if Docker daemon is running"""
        try:
            result = subprocess.run(
                ["docker", "ps"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.log("✓ Docker is running")
                self.log("✓ System is ready to start")
                self.status_label.config(
                    text="✅ Ready to Start",
                    fg="#27ae60"
                )
            else:
                self.log("✗ Docker is not running")
                self.log("Please start Docker Desktop and try again")
                self.status_label.config(
                    text="⚠️ Docker Not Running",
                    fg="#e67e22"
                )
        except Exception as e:
            self.log(f"✗ Cannot connect to Docker: {e}")

    def show_docker_not_installed(self):
        """Show message about Docker installation"""
        self.log("✗ Docker is not installed")
        self.status_label.config(
            text="❌ Docker Not Found",
            fg="#e74c3c"
        )

        response = messagebox.askyesno(
            "Docker Required",
            "AI-SOC requires Docker Desktop for container orchestration.\n\n"
            "Would you like to download Docker Desktop now?\n\n"
            "Docker Desktop is freely available and requires approximately 5-10 minutes for installation."
        )

        if response:
            webbrowser.open("https://www.docker.com/products/docker-desktop/")

    def start_system(self):
        """Start all AI-SOC services"""
        self.is_running = True
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.progress.start()

        self.log("Starting AI-SOC services...")
        self.status_label.config(
            text="🔄 Starting Services...",
            fg="#3498db"
        )

        # Run in background thread
        thread = threading.Thread(target=self._start_services_thread)
        thread.daemon = True
        thread.start()

    def _start_services_thread(self):
        """Background thread to start services"""
        try:
            # Check/copy .env
            self.log("Configuring environment...")
            env_file = self.base_dir / ".env"
            if not env_file.exists():
                self.log("✗ .env file not found")
                self.root.after(0, lambda: self.show_env_error())
                return

            # Copy .env to docker-compose directory
            docker_compose_dir = self.base_dir / "docker-compose"
            docker_compose_env = docker_compose_dir / ".env"

            import shutil
            shutil.copy(env_file, docker_compose_env)
            self.log("✓ Environment configured")

            # Start SIEM stack
            self.log("Starting Wazuh SIEM...")
            self.root.after(0, lambda: self.update_services("Starting Wazuh Indexer..."))

            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose/phase1-siem-core-windows.yml", "up", "-d"],
                capture_output=True,
                text=True,
                cwd=str(self.base_dir)
            )

            if result.returncode == 0:
                self.log("✓ Wazuh SIEM started")
                self.root.after(0, lambda: self.update_services("✓ Wazuh Indexer"))
                self.root.after(0, lambda: self.update_services("✓ Wazuh Manager"))
                time.sleep(2)
            else:
                self.log(f"✗ Error starting SIEM: {result.stderr}")
                return

            # Start AI services
            self.log("Starting AI services...")
            self.root.after(0, lambda: self.update_services("Starting ML Inference..."))

            result = subprocess.run(
                ["docker", "compose", "-f", "docker-compose/ai-services.yml", "up", "-d"],
                capture_output=True,
                text=True,
                cwd=str(self.base_dir)
            )

            if result.returncode == 0:
                self.log("✓ AI services started")
                self.root.after(0, lambda: self.update_services("✓ ML Inference"))
                self.root.after(0, lambda: self.update_services("✓ Alert Triage"))
                self.root.after(0, lambda: self.update_services("✓ RAG Service"))
                self.root.after(0, lambda: self.update_services("✓ ChromaDB"))
            else:
                self.log(f"✗ Error starting AI services: {result.stderr}")

            # Wait for services to initialize
            self.log("Waiting for services to initialize...")
            time.sleep(10)

            # Check health
            self.root.after(0, self.check_services_health)

        except Exception as e:
            self.log(f"✗ Error: {e}")
            self.root.after(0, self.on_start_error)

    def check_services_health(self):
        """Check if services are healthy"""
        try:
            result = subprocess.run(
                ["docker", "ps", "--format", "{{.Names}}\t{{.Status}}"],
                capture_output=True,
                text=True
            )

            if result.returncode == 0:
                healthy_count = 0
                total_count = 0

                for line in result.stdout.strip().split('\n'):
                    if line:
                        total_count += 1
                        if 'healthy' in line.lower() or 'up' in line.lower():
                            healthy_count += 1

                self.log(f"Services health: {healthy_count}/{total_count} operational")

                if healthy_count > 0:
                    self.on_start_success()
                else:
                    self.log("⚠️ Services started but health check pending...")
                    self.root.after(5000, self.check_services_health)

        except Exception as e:
            self.log(f"Error checking health: {e}")
            self.on_start_error()

    def on_start_success(self):
        """Called when services start successfully"""
        self.progress.stop()
        self.status_label.config(
            text="✅ AI-SOC Running",
            fg="#27ae60"
        )
        self.dashboard_button.config(state=tk.NORMAL)
        self.log("✓ AI-SOC is ready!")
        self.log("Click 'Open Dashboard' to view the web interface")

        messagebox.showinfo(
            "Deployment Successful",
            "AI-SOC platform is now operational.\n\n"
            "Select 'Open Dashboard' to access the web-based monitoring interface."
        )

    def on_start_error(self):
        """Called when start fails"""
        self.progress.stop()
        self.status_label.config(
            text="❌ Start Failed",
            fg="#e74c3c"
        )
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)

    def show_env_error(self):
        """Show error about missing .env file"""
        messagebox.showerror(
            "Configuration Missing",
            ".env configuration file not found.\n\n"
            "Please ensure the .env file exists in the AI-SOC directory."
        )
        self.on_start_error()

    def stop_system(self):
        """Stop all AI-SOC services"""
        if not messagebox.askyesno(
            "Confirm Stop",
            "Are you sure you want to stop AI-SOC?"
        ):
            return

        self.log("Stopping AI-SOC services...")
        self.status_label.config(
            text="🔄 Stopping...",
            fg="#e67e22"
        )
        self.progress.start()

        thread = threading.Thread(target=self._stop_services_thread)
        thread.daemon = True
        thread.start()

    def _stop_services_thread(self):
        """Background thread to stop services"""
        try:
            # Stop AI services
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose/ai-services.yml", "down"],
                capture_output=True,
                cwd=str(self.base_dir)
            )
            self.log("✓ AI services stopped")

            # Stop SIEM
            subprocess.run(
                ["docker", "compose", "-f", "docker-compose/phase1-siem-core-windows.yml", "down"],
                capture_output=True,
                cwd=str(self.base_dir)
            )
            self.log("✓ SIEM stopped")

            self.root.after(0, self.on_stop_success)

        except Exception as e:
            self.log(f"✗ Error stopping: {e}")

    def on_stop_success(self):
        """Called when services stop successfully"""
        self.progress.stop()
        self.is_running = False
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.dashboard_button.config(state=tk.DISABLED)
        self.status_label.config(
            text="⚪ System Stopped",
            fg="#7f8c8d"
        )
        self.services_text.config(state=tk.NORMAL)
        self.services_text.delete(1.0, tk.END)
        self.services_text.insert(tk.END, "All services stopped.\n")
        self.services_text.config(state=tk.DISABLED)
        self.log("✓ AI-SOC stopped successfully")

    def open_dashboard(self):
        """Open the web dashboard"""
        self.log("Opening dashboard in browser...")
        webbrowser.open("http://localhost:3000")

def main():
    """Main entry point"""
    root = tk.Tk()
    app = AISOCLauncher(root)
    root.mainloop()

if __name__ == "__main__":
    main()
