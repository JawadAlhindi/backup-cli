#!/usr/bin/env python3
"""
Google Drive Backup Tool - CLI Version
Interactive command-line interface for backing up Google Drive
"""

import subprocess
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Configuration
CONFIG_FILE = "config.json"
TEMP_DIR = "temp_data"
LOG_DIR = "logs"

# Create directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'
    
    # Background colors
    BG_GREEN = '\033[102m'
    BG_YELLOW = '\033[103m'
    BG_RED = '\033[101m'

def colored(text, color):
    """Return colored text"""
    return f"{color}{text}{Colors.END}"

def print_header(text):
    """Print a formatted header"""
    width = 70
    print("\n" + "=" * width)
    print(colored(text.center(width), Colors.BOLD + Colors.CYAN))
    print("=" * width + "\n")

def print_section(text):
    """Print a section header"""
    print("\n" + colored(f"▶ {text}", Colors.BOLD + Colors.BLUE))
    print("-" * 70)

def print_success(text):
    """Print success message"""
    print(colored(f"✅ {text}", Colors.GREEN))

def print_error(text):
    """Print error message"""
    print(colored(f"❌ {text}", Colors.RED))

def print_warning(text):
    """Print warning message"""
    print(colored(f"⚠️  {text}", Colors.YELLOW))

def print_info(text):
    """Print info message"""
    print(colored(f"ℹ️  {text}", Colors.CYAN))

def format_size(bytes_size):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def load_config():
    """Load configuration from file"""
    default_config = {
        'source': 'gdrive:',
        'destination': '',
        'rclone_path': 'rclone'
    }
    
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            return default_config
    return default_config

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def run_rclone_command(args, show_output=False, capture_output=True):
    """Run rclone command"""
    config = load_config()
    cmd = [config.get('rclone_path', 'rclone')] + args
    
    try:
        if show_output:
            result = subprocess.run(cmd, text=True)
            return result
        else:
            result = subprocess.run(
                cmd,
                capture_output=capture_output,
                text=True,
                timeout=300
            )
            return result
    except subprocess.TimeoutExpired:
        print_error("Command timeout")
        return None
    except FileNotFoundError:
        print_error("rclone not found. Please install rclone first.")
        return None
    except Exception as e:
        print_error(f"Error running rclone: {e}")
        return None

def check_rclone():
    """Check if rclone is installed and configured"""
    print_section("System Check")
    
    # Check rclone installed
    result = run_rclone_command(['version'])
    if not result or result.returncode != 0:
        print_error("rclone is not installed")
        print_info("Install from: https://rclone.org/downloads/")
        return False
    
    version = result.stdout.split('\n')[0]
    print_success(f"rclone installed: {version}")
    
    # Check gdrive configured
    result = run_rclone_command(['listremotes'])
    if result and 'gdrive:' in result.stdout:
        print_success("Google Drive (gdrive:) is configured")
        return True
    else:
        print_error("Google Drive remote 'gdrive:' not found")
        print_info("Run: rclone config")
        return False

def configure_settings():
    """Interactive configuration"""
    print_section("Configuration")
    
    config = load_config()
    
    print(f"\nCurrent settings:")
    print(f"  Source: {colored(config['source'], Colors.CYAN)}")
    print(f"  Destination: {colored(config['destination'] or '(not set)', Colors.CYAN)}")
    
    print("\n" + colored("Press Enter to keep current value, or type new value:", Colors.YELLOW))
    
    # Source
    source = input(f"\nSource [{config['source']}]: ").strip()
    if source:
        config['source'] = source
    
    # Destination
    dest = input(f"Destination [{config['destination']}]: ").strip()
    if dest:
        config['destination'] = dest
    
    if not config['destination']:
        print_error("Destination must be set!")
        return
    
    save_config(config)
    print_success("Configuration saved!")

def show_progress_bar(percent, width=50):
    """Display a progress bar"""
    filled = int(width * percent / 100)
    bar = '█' * filled + '░' * (width - filled)
    print(f"\r{colored('Progress:', Colors.CYAN)} [{bar}] {percent}%", end='', flush=True)

def scan_changes():
    """Scan for changes between Google Drive and local backup"""
    print_section("Scanning for Changes")
    
    config = load_config()
    if not config['destination']:
        print_error("Destination not configured. Run 'Configure Settings' first.")
        return None
    
    source = config['source']
    dest = config['destination']
    
    print_info("This will compare files without downloading them...")
    print()
    
    # Step 1: Get Google Drive files
    print("📥 Fetching Google Drive file list...")
    show_progress_bar(10)
    
    result = run_rclone_command([
        'lsjson',
        source,
        '--recursive',
        '--files-only'
    ])
    
    if not result or result.returncode != 0:
        print()
        print_error("Failed to fetch Google Drive files")
        return None
    
    drive_files = json.loads(result.stdout)
    show_progress_bar(40)
    print()
    
    # Step 2: Get local files
    print("💾 Fetching local file list...")
    
    if os.path.exists(dest):
        result = run_rclone_command([
            'lsjson',
            dest,
            '--recursive',
            '--files-only'
        ])
        
        if result and result.returncode == 0:
            local_files = json.loads(result.stdout)
        else:
            local_files = []
    else:
        local_files = []
    
    show_progress_bar(70)
    print()
    
    # Step 3: Compare
    print("🔍 Comparing files...")
    
    drive_dict = {item['Path']: item for item in drive_files}
    local_dict = {item['Path']: item for item in local_files}
    
    new_files = []
    changed_files = []
    deleted_files = []
    total_new_size = 0
    total_deleted_size = 0
    
    # Find new and changed files
    for path, drive_item in drive_dict.items():
        if path not in local_dict:
            new_files.append({
                'path': path,
                'size': drive_item['Size'],
                'modified': drive_item['ModTime']
            })
            total_new_size += drive_item['Size']
        else:
            local_item = local_dict[path]
            if (drive_item['Size'] != local_item['Size'] or 
                drive_item['ModTime'] != local_item['ModTime']):
                changed_files.append({
                    'path': path,
                    'old_size': local_item['Size'],
                    'new_size': drive_item['Size'],
                    'size_diff': drive_item['Size'] - local_item['Size'],
                    'modified': drive_item['ModTime']
                })
    
    # Find deleted files
    for path, local_item in local_dict.items():
        if path not in drive_dict:
            deleted_files.append({
                'path': path,
                'size': local_item['Size'],
                'modified': local_item['ModTime']
            })
            total_deleted_size += local_item['Size']
    
    show_progress_bar(100)
    print("\n")
    
    return {
        'new_files': new_files,
        'changed_files': changed_files,
        'deleted_files': deleted_files,
        'total_new_size': total_new_size,
        'total_deleted_size': total_deleted_size
    }

def display_changes(changes):
    """Display changes in a formatted way"""
    if not changes:
        return
    
    new_count = len(changes['new_files'])
    changed_count = len(changes['changed_files'])
    deleted_count = len(changes['deleted_files'])
    total = new_count + changed_count + deleted_count
    
    # Summary
    print_section("Change Summary")
    print()
    
    # Create summary boxes
    print("  ┌─────────────────────────────────────────────────────────┐")
    print(f"  │ {colored('NEW FILES', Colors.GREEN):70s} │")
    print(f"  │   Count: {colored(str(new_count), Colors.BOLD):62s} │")
    print(f"  │   Size:  {colored(format_size(changes['total_new_size']), Colors.BOLD):62s} │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print(f"  │ {colored('CHANGED FILES', Colors.YELLOW):70s} │")
    print(f"  │   Count: {colored(str(changed_count), Colors.BOLD):62s} │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print(f"  │ {colored('DELETED FILES', Colors.RED):70s} │")
    print(f"  │   Count: {colored(str(deleted_count), Colors.BOLD):62s} │")
    print(f"  │   Space: {colored(format_size(changes['total_deleted_size']) + ' will be freed', Colors.BOLD):62s} │")
    print("  └─────────────────────────────────────────────────────────┘")
    print()
    
    if total == 0:
        print_success("✨ No changes detected! Everything is up to date.")
        return False
    
    # Ask if user wants to see details
    print(f"\nTotal changes: {colored(str(total), Colors.BOLD)}")
    response = input("\nShow detailed file list? (Y/n): ").strip().lower()
    
    if response != 'n':
        show_detailed_changes(changes)
    
    return True

def show_detailed_changes(changes):
    """Show detailed list of changed files"""
    
    # New files
    if changes['new_files']:
        print_section(f"New Files ({len(changes['new_files'])})")
        print()
        
        for i, file in enumerate(changes['new_files'][:50], 1):
            size = format_size(file['size'])
            print(f"  {colored('➕', Colors.GREEN)} {file['path']:<50} {colored(size, Colors.CYAN):>12}")
        
        if len(changes['new_files']) > 50:
            remaining = len(changes['new_files']) - 50
            print(f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")
    
    # Changed files
    if changes['changed_files']:
        print_section(f"Changed Files ({len(changes['changed_files'])})")
        print()
        
        for i, file in enumerate(changes['changed_files'][:50], 1):
            old_size = format_size(file['old_size'])
            new_size = format_size(file['new_size'])
            arrow = '↑' if file['size_diff'] > 0 else '↓'
            print(f"  {colored('📝', Colors.YELLOW)} {file['path']:<40} {old_size} → {new_size} {arrow}")
        
        if len(changes['changed_files']) > 50:
            remaining = len(changes['changed_files']) - 50
            print(f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")
    
    # Deleted files
    if changes['deleted_files']:
        print_section(f"Deleted Files ({len(changes['deleted_files'])})")
        print()
        
        for i, file in enumerate(changes['deleted_files'][:50], 1):
            size = format_size(file['size'])
            print(f"  {colored('🗑️ ', Colors.RED)} {file['path']:<50} {colored(size, Colors.CYAN):>12}")
        
        if len(changes['deleted_files']) > 50:
            remaining = len(changes['deleted_files']) - 50
            print(f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")
    
    print()

def export_changes(changes):
    """Export changes to a text file"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = os.path.join(TEMP_DIR, f'changes_report_{timestamp}.txt')
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("GOOGLE DRIVE BACKUP - CHANGE REPORT\n")
        f.write("=" * 70 + "\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 70 + "\n\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 70 + "\n")
        f.write(f"New files:     {len(changes['new_files'])} ({format_size(changes['total_new_size'])})\n")
        f.write(f"Changed files: {len(changes['changed_files'])}\n")
        f.write(f"Deleted files: {len(changes['deleted_files'])} ({format_size(changes['total_deleted_size'])})\n")
        f.write("\n")
        
        # New files
        f.write(f"NEW FILES: {len(changes['new_files'])}\n")
        f.write("-" * 70 + "\n")
        for item in changes['new_files']:
            f.write(f"+ {item['path']} ({format_size(item['size'])})\n")
        f.write("\n")
        
        # Changed files
        f.write(f"CHANGED FILES: {len(changes['changed_files'])}\n")
        f.write("-" * 70 + "\n")
        for item in changes['changed_files']:
            old = format_size(item['old_size'])
            new = format_size(item['new_size'])
            f.write(f"~ {item['path']} ({old} → {new})\n")
        f.write("\n")
        
        # Deleted files
        f.write(f"DELETED FILES: {len(changes['deleted_files'])}\n")
        f.write("-" * 70 + "\n")
        for item in changes['deleted_files']:
            f.write(f"- {item['path']} ({format_size(item['size'])})\n")
    
    print_success(f"Report exported to: {filename}")
    return filename

def apply_changes():
    """Apply changes by syncing files"""
    print_section("Applying Changes")
    
    config = load_config()
    source = config['source']
    dest = config['destination']
    
    # Confirm
    print()
    print_warning("This will modify your backup files!")
    response = input("\nAre you sure you want to continue? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print_info("Sync cancelled.")
        return
    
    # Create log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(LOG_DIR, f'backup_{timestamp}.log')
    
    print()
    print_info("Starting synchronization...")
    print_info(f"Log file: {log_file}")
    print()
    
    # Run sync with progress
    result = run_rclone_command([
        'sync',
        source,
        dest,
        '--progress',
        '--checksum',
        '--track-renames',
        '--delete-after',
        '--log-file', log_file,
        '--log-level', 'INFO',
        '--stats', '1s',
        '--stats-one-line'
    ], show_output=True, capture_output=False)
    
    print()
    if result and result.returncode == 0:
        print_success("✅ Backup completed successfully!")
        print_info(f"Log saved to: {log_file}")
    else:
        print_error("❌ Sync failed. Check log for details.")
        print_info(f"Log file: {log_file}")

def main_menu():
    """Display main menu and handle user input"""
    while True:
        print_header("GOOGLE DRIVE BACKUP TOOL - CLI")
        
        config = load_config()
        dest_status = colored(config['destination'] or "Not configured", 
                            Colors.GREEN if config['destination'] else Colors.RED)
        
        print(f"Current destination: {dest_status}")
        print()
        
        print(colored("Main Menu:", Colors.BOLD))
        print()
        print("  1. " + colored("Configure Settings", Colors.CYAN))
        print("  2. " + colored("Scan for Changes", Colors.CYAN))
        print("  3. " + colored("Apply Changes (Sync)", Colors.CYAN))
        print("  4. " + colored("Check System", Colors.CYAN))
        print("  5. " + colored("Help", Colors.CYAN))
        print("  6. " + colored("Exit", Colors.CYAN))
        print()
        
        choice = input(colored("Enter your choice (1-6): ", Colors.BOLD)).strip()
        
        if choice == '1':
            configure_settings()
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            changes = scan_changes()
            if changes:
                has_changes = display_changes(changes)
                if has_changes:
                    print()
                    response = input("Export report? (y/N): ").strip().lower()
                    if response == 'y':
                        export_changes(changes)
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            if not config['destination']:
                print_error("Please configure destination first (Option 1)")
                input("\nPress Enter to continue...")
                continue
            
            print_info("Scanning for changes first...")
            changes = scan_changes()
            if changes:
                has_changes = display_changes(changes)
                if has_changes:
                    print()
                    apply_changes()
                else:
                    print_info("Nothing to sync!")
            input("\nPress Enter to continue...")
            
        elif choice == '4':
            check_rclone()
            input("\nPress Enter to continue...")
            
        elif choice == '5':
            show_help()
            input("\nPress Enter to continue...")
            
        elif choice == '6':
            print()
            print_success("Thank you for using Google Drive Backup Tool!")
            print()
            sys.exit(0)
            
        else:
            print_error("Invalid choice. Please enter 1-6.")
            input("\nPress Enter to continue...")

def show_help():
    """Show help information"""
    print_section("Help & Usage Guide")
    print()
    print(colored("Quick Start:", Colors.BOLD))
    print("  1. Configure Settings - Set your backup destination")
    print("  2. Scan for Changes - See what will be synced")
    print("  3. Apply Changes - Perform the actual backup")
    print()
    print(colored("How It Works:", Colors.BOLD))
    print("  • Scanning is FAST - doesn't download files")
    print("  • Only changed/new files are synced")
    print("  • Green = New files to download")
    print("  • Yellow = Files to update")
    print("  • Red = Files to delete from backup")
    print()
    print(colored("First Time Setup:", Colors.BOLD))
    print("  1. Make sure rclone is installed and configured")
    print("  2. Run 'Check System' to verify")
    print("  3. Configure your destination folder")
    print("  4. Scan and apply changes")
    print()
    print(colored("Regular Backups:", Colors.BOLD))
    print("  • Just run 'Scan for Changes' weekly/monthly")
    print("  • Review what changed")
    print("  • Apply if satisfied")
    print()
    print(colored("Tips:", Colors.BOLD))
    print("  • First backup downloads everything (slow)")
    print("  • After that, only changes sync (fast)")
    print("  • Always review before applying")
    print("  • Export reports for your records")
    print()

if __name__ == '__main__':
    try:
        main_menu()
    except KeyboardInterrupt:
        print("\n")
        print_info("Interrupted by user")
        print()
        sys.exit(0)
    except Exception as e:
        print()
        print_error(f"Unexpected error: {e}")
        print()
        sys.exit(1)