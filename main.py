#!/usr/bin/env python3
"""
Google Drive Backup Tool - CLI Version with Auto-Install
Interactive command-line interface for backing up Google Drive

Features:
- Automatic rclone installation if not found
- Fast change detection (metadata comparison only)
- Colored terminal output
- Preview changes before syncing
- Export reports to text files
- Progress bars and real-time status
- Safe sync with confirmation
"""

import subprocess
import json
import os
import sys
import platform
import urllib.request
import zipfile
import tarfile
import shutil
from datetime import datetime
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

CONFIG_FILE = "config.json"
TEMP_DIR = "temp_data"
LOG_DIR = "logs"
RCLONE_DIR = "rclone_bin"  # Local rclone installation directory

# Create directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(RCLONE_DIR, exist_ok=True)

# ============================================================================
# TERMINAL COLORS
# ============================================================================


class Colors:
    """ANSI color codes for terminal output"""
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

# ============================================================================
# DISPLAY UTILITIES
# ============================================================================


def colored(text, color):
    """Return colored text for terminal output"""
    return f"{color}{text}{Colors.END}"


def print_header(text):
    """Print a formatted header with borders"""
    width = 70
    print("\n" + "=" * width)
    print(colored(text.center(width), Colors.BOLD + Colors.CYAN))
    print("=" * width + "\n")


def print_section(text):
    """Print a section header"""
    print("\n" + colored(f"▶ {text}", Colors.BOLD + Colors.BLUE))
    print("-" * 70)


def print_success(text):
    """Print success message in green"""
    print(colored(f"✅ {text}", Colors.GREEN))


def print_error(text):
    """Print error message in red"""
    print(colored(f"❌ {text}", Colors.RED))


def print_warning(text):
    """Print warning message in yellow"""
    print(colored(f"⚠️  {text}", Colors.YELLOW))


def print_info(text):
    """Print info message in cyan"""
    print(colored(f"ℹ️  {text}", Colors.CYAN))


def format_size(bytes_size):
    """Format bytes to human readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"


def show_progress_bar(percent, width=50):
    """Display a progress bar in the terminal"""
    filled = int(width * percent / 100)
    bar = '█' * filled + '░' * (width - filled)
    print(
        f"\r{colored('Progress:', Colors.CYAN)} [{bar}] {percent}%", end='', flush=True)

# ============================================================================
# RCLONE AUTO-INSTALLATION
# ============================================================================


def get_rclone_download_url():
    """
    Get the appropriate rclone download URL based on OS and architecture

    Returns:
        tuple: (download_url, is_zip_file)
    """
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Determine architecture
    if machine in ['x86_64', 'amd64']:
        arch = 'amd64'
    elif machine in ['i386', 'i686', 'x86']:
        arch = '386'
    elif machine in ['arm64', 'aarch64']:
        arch = 'arm64'
    elif machine.startswith('arm'):
        arch = 'arm'
    else:
        arch = 'amd64'  # Default to amd64

    base_url = "https://downloads.rclone.org/v1.68.2"

    if system == 'windows':
        return (f"{base_url}/rclone-v1.68.2-windows-{arch}.zip", True)
    elif system == 'darwin':  # macOS
        return (f"{base_url}/rclone-v1.68.2-osx-{arch}.zip", True)
    elif system == 'linux':
        return (f"{base_url}/rclone-v1.68.2-linux-{arch}.zip", True)
    else:
        return (f"{base_url}/rclone-v1.68.2-linux-amd64.zip", True)


def download_file(url, destination):
    """
    Download a file with progress reporting

    Args:
        url: URL to download from
        destination: Local file path to save to
    """
    print_info(f"Downloading from: {url}")

    def report_progress(block_num, block_size, total_size):
        downloaded = block_num * block_size
        if total_size > 0:
            percent = min(int(downloaded * 100 / total_size), 100)
            show_progress_bar(percent)

    try:
        urllib.request.urlretrieve(
            url, destination, reporthook=report_progress)
        print()  # New line after progress bar
        print_success(f"Downloaded to: {destination}")
        return True
    except Exception as e:
        print()
        print_error(f"Download failed: {e}")
        return False


def extract_archive(archive_path, extract_to):
    """
    Extract zip or tar archive

    Args:
        archive_path: Path to archive file
        extract_to: Directory to extract to
    """
    print_info("Extracting archive...")

    try:
        if archive_path.endswith('.zip'):
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(extract_to)
        elif archive_path.endswith(('.tar.gz', '.tgz')):
            with tarfile.open(archive_path, 'r:gz') as tar_ref:
                tar_ref.extractall(extract_to)

        print_success("Extraction completed")
        return True
    except Exception as e:
        print_error(f"Extraction failed: {e}")
        return False


def find_rclone_executable(directory):
    """
    Find rclone executable in extracted directory

    Args:
        directory: Directory to search in

    Returns:
        Path to rclone executable or None
    """
    exe_name = 'rclone.exe' if platform.system().lower() == 'windows' else 'rclone'

    # Search recursively
    for root, dirs, files in os.walk(directory):
        if exe_name in files:
            return os.path.join(root, exe_name)

    return None


def install_rclone():
    """
    Download and install rclone locally

    Returns:
        Path to rclone executable or None if failed
    """
    print_section("Installing rclone")

    # Get download URL
    download_url, is_zip = get_rclone_download_url()

    # Prepare paths
    archive_name = download_url.split('/')[-1]
    archive_path = os.path.join(TEMP_DIR, archive_name)

    # Download
    if not download_file(download_url, archive_path):
        return None

    # Extract
    if not extract_archive(archive_path, RCLONE_DIR):
        return None

    # Find rclone executable
    rclone_path = find_rclone_executable(RCLONE_DIR)

    if rclone_path:
        # Make executable on Unix-like systems
        if platform.system().lower() != 'windows':
            os.chmod(rclone_path, 0o755)

        print_success(f"rclone installed: {rclone_path}")

        # Clean up archive
        try:
            os.remove(archive_path)
        except:
            pass

        return rclone_path
    else:
        print_error("Could not find rclone executable in extracted files")
        return None


def find_rclone():
    """
    Find rclone executable, install if not found

    Returns:
        Path to rclone executable
    """
    # First, check if rclone is in PATH
    if shutil.which('rclone'):
        return 'rclone'

    # Check local installation
    exe_name = 'rclone.exe' if platform.system().lower() == 'windows' else 'rclone'
    local_rclone = find_rclone_executable(RCLONE_DIR)

    if local_rclone and os.path.exists(local_rclone):
        return local_rclone

    # Not found - offer to install
    print_warning("rclone not found on your system")
    response = input(
        "\nWould you like to download and install rclone now? (Y/n): ").strip().lower()

    if response in ['', 'y', 'yes']:
        rclone_path = install_rclone()
        if rclone_path:
            return rclone_path
        else:
            print_error("Failed to install rclone automatically")
            print_info(
                "Please install manually from: https://rclone.org/downloads/")
            return None
    else:
        print_info(
            "Please install rclone manually from: https://rclone.org/downloads/")
        return None

# ============================================================================
# CONFIGURATION MANAGEMENT
# ============================================================================


def load_config():
    """Load configuration from JSON file"""
    default_config = {
        'source': 'gdrive:',
        'destination': '',
        'rclone_path': None  # Will be auto-detected
    }

    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Ensure rclone_path exists
                if 'rclone_path' not in config or not config['rclone_path']:
                    config['rclone_path'] = find_rclone()
                return config
        except:
            return default_config

    return default_config


def save_config(config):
    """Save configuration to JSON file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

# ============================================================================
# RCLONE INTERFACE
# ============================================================================


def run_rclone_command(args, show_output=False, capture_output=True):
    """
    Run rclone command safely

    Args:
        args: List of command arguments
        show_output: Whether to show output in real-time
        capture_output: Whether to capture output for processing

    Returns:
        subprocess.CompletedProcess or None
    """
    config = load_config()
    rclone_path = config.get('rclone_path')

    # Find rclone if not configured
    if not rclone_path or not os.path.exists(rclone_path):
        rclone_path = find_rclone()
        if not rclone_path:
            return None
        config['rclone_path'] = rclone_path
        save_config(config)

    cmd = [rclone_path] + args

    try:
        if show_output:
            # Show output in real-time (for sync operations)
            result = subprocess.run(cmd, text=True)
            return result
        else:
            # Capture output for processing
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
        print_error("rclone executable not found")
        return None
    except Exception as e:
        print_error(f"Error running rclone: {e}")
        return None

# ============================================================================
# SYSTEM VERIFICATION
# ============================================================================


def check_rclone():
    """Check if rclone is installed and Google Drive is configured"""
    print_section("System Check")

    # Find or install rclone
    config = load_config()
    rclone_path = config.get('rclone_path')

    if not rclone_path or not os.path.exists(rclone_path):
        rclone_path = find_rclone()
        if not rclone_path:
            return False
        config['rclone_path'] = rclone_path
        save_config(config)

    # Check rclone version
    result = run_rclone_command(['version'])
    if not result or result.returncode != 0:
        print_error("rclone is not working properly")
        return False

    version = result.stdout.split('\n')[0]
    print_success(f"rclone installed: {version}")
    print_info(f"Location: {rclone_path}")

    # Check gdrive configured
    result = run_rclone_command(['listremotes'])
    if result and 'gdrive:' in result.stdout:
        print_success("Google Drive (gdrive:) is configured")
        return True
    else:
        print_error("Google Drive remote 'gdrive:' not found")
        print_info("Run: rclone config")
        print_info("Or use the built-in configuration wizard")
        return False

# ============================================================================
# CONFIGURATION INTERFACE
# ============================================================================


def configure_rclone_gdrive():
    """
    Interactive wizard to configure Google Drive in rclone
    """
    print_section("Configure Google Drive")
    print()
    print_info("This will launch rclone's configuration wizard")
    print_info("Follow these steps:")
    print("  1. Choose: n (new remote)")
    print("  2. Name: gdrive")
    print("  3. Storage: choose 'Google Drive' number")
    print("  4. Client ID/Secret: press Enter (leave blank)")
    print("  5. Scope: 1 (full access)")
    print("  6. Root folder: press Enter (leave blank)")
    print("  7. Service Account: press Enter (leave blank)")
    print("  8. Auto config: y (will open browser)")
    print("  9. Team Drive: n")
    print("  10. Confirm: y")
    print()

    response = input("Ready to configure? (Y/n): ").strip().lower()
    if response in ['', 'y', 'yes']:
        run_rclone_command(['config'], show_output=True, capture_output=False)


def configure_settings():
    """Interactive configuration wizard"""
    print_section("Configuration")

    config = load_config()

    print(f"\nCurrent settings:")
    print(f"  Source: {colored(config['source'], Colors.CYAN)}")
    print(
        f"  Destination: {colored(config['destination'] or '(not set)', Colors.CYAN)}")
    print(
        f"  rclone: {colored(config.get('rclone_path', 'auto-detect'), Colors.CYAN)}")

    print("\n" + colored("Press Enter to keep current value, or type new value:", Colors.YELLOW))

    # Source configuration
    source = input(f"\nSource [{config['source']}]: ").strip()
    if source:
        config['source'] = source

    # Destination configuration
    dest = input(f"Destination [{config['destination']}]: ").strip()
    if dest:
        config['destination'] = dest

    if not config['destination']:
        print_error("Destination must be set!")
        return

    save_config(config)
    print_success("Configuration saved!")

# ============================================================================
# CHANGE DETECTION
# ============================================================================


def scan_changes():
    """
    Scan for changes between Google Drive and local backup

    This performs a fast comparison using metadata only (no file downloads)

    Returns:
        Dictionary containing new_files, changed_files, deleted_files and totals
        or None if error occurs
    """
    print_section("Scanning for Changes")

    config = load_config()
    if not config['destination']:
        print_error(
            "Destination not configured. Run 'Configure Settings' first.")
        return None

    source = config['source']
    dest = config['destination']

    print_info("This will compare files without downloading them...")
    print()

    # Step 1: Get Google Drive file list
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

    # Step 2: Get local file list
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

    # Step 3: Compare and categorize files
    print("🔍 Comparing files...")

    # Create dictionaries for fast lookup
    drive_dict = {item['Path']: item for item in drive_files}
    local_dict = {item['Path']: item for item in local_files}

    # Initialize result containers
    new_files = []
    changed_files = []
    deleted_files = []
    total_new_size = 0
    total_deleted_size = 0

    # Find new and changed files
    for path, drive_item in drive_dict.items():
        if path not in local_dict:
            # File exists in Drive but not locally = NEW
            new_files.append({
                'path': path,
                'size': drive_item['Size'],
                'modified': drive_item['ModTime']
            })
            total_new_size += drive_item['Size']
        else:
            # File exists in both - check if changed
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
            # File exists locally but not in Drive = DELETED
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

# ============================================================================
# CHANGE DISPLAY
# ============================================================================


def display_changes(changes):
    """
    Display changes summary in a formatted way

    Args:
        changes: Dictionary containing change information

    Returns:
        True if there are changes, False otherwise
    """
    if not changes:
        return

    new_count = len(changes['new_files'])
    changed_count = len(changes['changed_files'])
    deleted_count = len(changes['deleted_files'])
    total = new_count + changed_count + deleted_count

    # Display summary boxes
    print_section("Change Summary")
    print()

    print("  ┌─────────────────────────────────────────────────────────┐")
    print(f"  │ {colored('NEW FILES', Colors.GREEN):70s} │")
    print(f"  │   Count: {colored(str(new_count), Colors.BOLD):62s} │")
    print(
        f"  │   Size:  {colored(format_size(changes['total_new_size']), Colors.BOLD):62s} │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print(f"  │ {colored('CHANGED FILES', Colors.YELLOW):70s} │")
    print(f"  │   Count: {colored(str(changed_count), Colors.BOLD):62s} │")
    print("  ├─────────────────────────────────────────────────────────┤")
    print(f"  │ {colored('DELETED FILES', Colors.RED):70s} │")
    print(f"  │   Count: {colored(str(deleted_count), Colors.BOLD):62s} │")
    print(
        f"  │   Space: {colored(format_size(changes['total_deleted_size']) + ' will be freed', Colors.BOLD):62s} │")
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
    """Show detailed list of all changed files"""

    # Display new files
    if changes['new_files']:
        print_section(f"New Files ({len(changes['new_files'])})")
        print()

        for i, file in enumerate(changes['new_files'][:50], 1):
            size = format_size(file['size'])
            print(
                f"  {colored('➕', Colors.GREEN)} {file['path']:<50} {colored(size, Colors.CYAN):>12}")

        if len(changes['new_files']) > 50:
            remaining = len(changes['new_files']) - 50
            print(
                f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")

    # Display changed files
    if changes['changed_files']:
        print_section(f"Changed Files ({len(changes['changed_files'])})")
        print()

        for i, file in enumerate(changes['changed_files'][:50], 1):
            old_size = format_size(file['old_size'])
            new_size = format_size(file['new_size'])
            arrow = '↑' if file['size_diff'] > 0 else '↓'
            print(
                f"  {colored('📝', Colors.YELLOW)} {file['path']:<40} {old_size} → {new_size} {arrow}")

        if len(changes['changed_files']) > 50:
            remaining = len(changes['changed_files']) - 50
            print(
                f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")

    # Display deleted files
    if changes['deleted_files']:
        print_section(f"Deleted Files ({len(changes['deleted_files'])})")
        print()

        for i, file in enumerate(changes['deleted_files'][:50], 1):
            size = format_size(file['size'])
            print(
                f"  {colored('🗑️ ', Colors.RED)} {file['path']:<50} {colored(size, Colors.CYAN):>12}")

        if len(changes['deleted_files']) > 50:
            remaining = len(changes['deleted_files']) - 50
            print(
                f"\n  {colored(f'... and {remaining} more files', Colors.YELLOW)}")

    print()

# ============================================================================
# REPORT EXPORT
# ============================================================================


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
        f.write(
            f"New files:     {len(changes['new_files'])} ({format_size(changes['total_new_size'])})\n")
        f.write(f"Changed files: {len(changes['changed_files'])}\n")
        f.write(
            f"Deleted files: {len(changes['deleted_files'])} ({format_size(changes['total_deleted_size'])})\n")
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

# ============================================================================
# SYNC OPERATION
# ============================================================================


def apply_changes():
    """Apply changes by syncing files from Google Drive to local backup"""
    print_section("Applying Changes")

    config = load_config()
    source = config['source']
    dest = config['destination']

    # Confirm with user
    print()
    print_warning("This will modify your backup files!")
    response = input(
        "\nAre you sure you want to continue? (yes/no): ").strip().lower()

    if response not in ['yes', 'y']:
        print_info("Sync cancelled.")
        return

    # Create timestamped log file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(LOG_DIR, f'backup_{timestamp}.log')

    print()
    print_info("Starting synchronization...")
    print_info(f"Log file: {log_file}")
    print()

    # Run rclone sync with progress output
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

# ============================================================================
# HELP SYSTEM
# ============================================================================


def show_help():
    """Show help and usage information"""
    print_section("Help & Usage Guide")
    print()
    print(colored("Quick Start:", Colors.BOLD))
    print("  1. Configure Google Drive - Set up rclone connection")
    print("  2. Configure Settings - Set your backup destination")
    print("  3. Scan for Changes - See what will be synced")
    print("  4. Apply Changes - Perform the actual backup")
    print()
    print(colored("How It Works:", Colors.BOLD))
    print("  • rclone auto-installs if missing")
    print("  • Scanning is FAST - doesn't download files")
    print("  • Only changed/new files are synced")
    print("  • Green = New files to download")
    print("  • Yellow = Files to update")
    print("  • Red = Files to delete from backup")
    print()
    print(colored("First Time Setup:", Colors.BOLD))
    print("  1. Run 'Check System' - installs rclone if needed")
    print("  2. Run 'Configure Google Drive' - set up gdrive:")
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

# ============================================================================
# MAIN MENU
# ============================================================================


def main_menu():
    """Display main menu and handle user interactions"""
    while True:
        print_header("GOOGLE DRIVE BACKUP TOOL - CLI (AUTO-INSTALL)")

        config = load_config()
        dest_status = colored(config['destination'] or "Not configured",
                              Colors.GREEN if config['destination'] else Colors.RED)

        print(f"Current destination: {dest_status}")
        print()

        print(colored("Main Menu:", Colors.BOLD))
        print()
        print("  1. " + colored("Configure Google Drive (rclone)", Colors.CYAN))
        print("  2. " + colored("Configure Settings (destination)", Colors.CYAN))
        print("  3. " + colored("Scan for Changes", Colors.CYAN))
        print("  4. " + colored("Apply Changes (Sync)", Colors.CYAN))
        print("  5. " + colored("Check System", Colors.CYAN))
        print("  6. " + colored("Help", Colors.CYAN))
        print("  7. " + colored("Exit", Colors.CYAN))
        print()

        choice = input(
            colored("Enter your choice (1-7): ", Colors.BOLD)).strip()

        # Option 1: Configure Google Drive
        if choice == '1':
            configure_rclone_gdrive()
            input("\nPress Enter to continue...")

        # Option 2: Configure Settings
        elif choice == '2':
            configure_settings()
            input("\nPress Enter to continue...")

        # Option 3: Scan for Changes
        elif choice == '3':
            changes = scan_changes()
            if changes:
                has_changes = display_changes(changes)
                if has_changes:
                    print()
                    response = input("Export report? (y/N): ").strip().lower()
                    if response == 'y':
                        export_changes(changes)
            input("\nPress Enter to continue...")

        # Option 4: Apply Changes (Sync)
        elif choice == '4':
            if not config['destination']:
                print_error("Please configure destination first (Option 2)")
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

        # Option 5: Check System
        elif choice == '5':
            check_rclone()
            input("\nPress Enter to continue...")

        # Option 6: Help
        elif choice == '6':
            show_help()
            input("\nPress Enter to continue...")

        # Option 7: Exit
        elif choice == '7':
            print()
            print_success("Thank you for using Google Drive Backup Tool!")
            print()
            sys.exit(0)

        # Invalid choice
        else:
            print_error("Invalid choice. Please enter 1-7.")
            input("\nPress Enter to continue...")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


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
        import traceback
        traceback.print_exc()
        print()
        sys.exit(1)
