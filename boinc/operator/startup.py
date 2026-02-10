import logging
import signal
import threading
from time import sleep

from boinccmd import configure_boinc_projects, get_state


def configure_boinc_in_background(boinc_process, data_folder, options, should_terminate):
    """Background thread to wait for BOINC initialization and configure projects
    
    Args:
        boinc_process: The subprocess.Popen object for the BOINC client
        data_folder: Path to the BOINC data folder
        options: Configuration options dictionary
        should_terminate: threading.Event to signal termination needed
    """
    try:
        # Wait for BOINC client to initialize
        boinc_process_initialized = False
        while boinc_process.poll() is None and not boinc_process_initialized:
            boinc_process_initialized = get_state(data_folder)
            if boinc_process_initialized:
                logging.debug(f'BOINC client initialized')
            else:
                logging.debug(f'Waiting for BOINC client to initialize')
                # Sleep briefly before next check if not initialized
                sleep(0.5)
        
        # If process already terminated, exit thread
        if boinc_process.poll() is not None:
            return
        
        # Configure BOINC projects
        projects_configured = configure_boinc_projects(
            data_folder,
            options.get('account_manager_url'),
            options.get('account_manager_username'),
            options.get('account_manager_password')
        )
        
        if not projects_configured:
            logging.error('Failed to configure BOINC projects, terminating')
            should_terminate.set()
            boinc_process.send_signal(signal.SIGTERM)
            return
            
    except Exception as e:
        logging.error(f'Error in configuration thread: {e}')
        should_terminate.set()
        if boinc_process.poll() is None:
            boinc_process.send_signal(signal.SIGTERM)


def start_configuration_thread(boinc_process, data_folder, options, should_terminate):
    """Start the background configuration thread
    
    Args:
        boinc_process: The subprocess.Popen object for the BOINC client
        data_folder: Path to the BOINC data folder
        options: Configuration options dictionary
        should_terminate: threading.Event to signal termination needed
        
    Returns:
        threading.Thread: The started configuration thread
    """
    config_thread = threading.Thread(
        target=configure_boinc_in_background,
        args=(boinc_process, data_folder, options, should_terminate),
        daemon=True
    )
    config_thread.start()
    return config_thread
