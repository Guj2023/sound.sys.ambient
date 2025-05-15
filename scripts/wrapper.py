import os
import platform
import subprocess
import time
import threading
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import ThreadingOSCUDPServer

class OscSender:
    """Python equivalent of OscSender.ts"""
    def __init__(self, port: int, host: str = "127.0.0.1"):
        self.client = udp_client.SimpleUDPClient(host, port)

    def send(self, address: str, *args):
        """Send OSC message to the specified address with args"""
        self.client.send_message(address, args)


class SonicPiWrapper:
    """Main wrapper class for Sonic Pi server communication"""

    def __init__(self, config=None):
        # Set platform-specific defaults
        self.platform = platform.system().lower()

        if self.platform == "windows":
            self.root_path = r'C:\Program Files\Sonic Pi'
            self.ruby_path = os.path.join(self.root_path, r'app\server\native\ruby\bin\ruby.exe')
        elif self.platform == "darwin":  # macOS
            self.root_path = '/Applications/Sonic Pi.app/Contents/Resources'
            self.ruby_path = '/usr/bin/ruby'
        else:  # Linux
            self.root_path = '/home/user/sonic-pi'
            self.ruby_path = 'ruby'

        # Configuration
        self.config = config or {}

        # Override defaults if specified in config
        if self.config.get('sonicPiRootDirectory'):
            self.root_path = self.config['sonicPiRootDirectory']

        if self.config.get('commandPath'):
            self.ruby_path = self.config['commandPath']
        # Set up paths
        self.daemon_launcher_path = os.path.join(self.root_path, 'server/ruby/bin/daemon.rb')
        if self.platform == "windows":
            self.daemon_launcher_path = os.path.join(self.root_path, r'app\server\ruby\bin\daemon.rb')

        self.sp_user_path = os.path.join(self.sonic_pi_home_path(), '.sonic-pi')
        self.daemon_log_path = os.path.join(self.sp_user_path, 'log/daemon.log')

        self.sample_path = os.path.join(self.root_path, 'etc/samples')
        self.sp_user_tmp_path = os.path.join(self.sp_user_path, '.writableTesterPath')
        self.log_path = os.path.join(self.sp_user_path, 'log')

        self.server_error_log_path = os.path.join(self.log_path, 'server-errors.log')
        self.server_output_log_path = os.path.join(self.log_path, 'server-output.log')
        self.gui_log_path = os.path.join(self.log_path, 'gui.log')
        self.process_log_path = os.path.join(self.log_path, 'processes.log')
        self.scsynth_log_path = os.path.join(self.log_path, 'scsynth.log')

        # Ports
        self.daemon_port = -1
        self.gui_send_to_server_port = -1
        self.gui_listen_to_server_port = -1
        self.server_listen_to_gui_port = -1
        self.server_osc_cues_port = -1
        self.server_send_to_gui_port = -1
        self.scsynth_port = -1
        self.scsynth_send_port = -1

        # State
        self.run_offset = 0
        self.server_started = False
        self.gui_uuid = -1

        # OSC clients
        self.server_sender = None
        self.daemon_sender = None

        # Create log directory if it doesn't exist
        if not os.path.exists(self.log_path):
            os.makedirs(self.log_path, exist_ok=True)

        # Callbacks
        self.on_log = None
        self.on_cue = None
        self.on_error = None
        self.on_syntax_error = None
        self.on_run_started = None
        self.on_run_ended = None

        self.osc_server = None

    def sonic_pi_home_path(self):
        """Return the home directory path"""
        return os.path.expanduser("~")

    def check_sonic_pi_path(self):
        """Check if the Sonic Pi paths are properly configured"""
        if not os.path.exists(self.daemon_launcher_path):
            return False
        return True

    def start_server(self):
        """Start the Sonic Pi server"""
        if self.server_started:
            return

        print("Starting Sonic Pi server...")

        # Start Ruby server and get ports
        success = self.start_ruby_server()
        if not success:
            print("Failed to start Ruby server")
            return False

        # Set up OSC receiver and keep-alive
        self.setup_osc_receiver()
        self.start_keep_alive()
        self.server_started = True

        # wait for the server to start
        time.sleep(4)

        # Update mixer settings
        self.update_mixer_settings()

        return True

    def start_ruby_server(self):
        """Start the Ruby server process"""
        args = [self.ruby_path, self.daemon_launcher_path]

        try:
            process = subprocess.Popen(
                args, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )

            # Read the output to get port information
            for line in iter(process.stdout.readline, ''):
                print(f"Daemon Out: {line.strip()}")

                # Parse ports from daemon output
                if line and line.strip() and len(line.strip().split()) >= 7:
                    ports = line.strip().split()

                    # Order: daemon-keep-alive gui-listen-to-server gui-send-to-server scsynth osc-cues tau-api tau-phx token
                    self.daemon_port = int(ports[0])
                    self.gui_listen_to_server_port = int(ports[1])
                    self.server_send_to_gui_port = int(ports[2])
                    self.gui_uuid = int(ports[7])

                    # Initialize OSC senders
                    self.server_sender = OscSender(self.server_send_to_gui_port)
                    self.daemon_sender = OscSender(self.daemon_port)
                    return True

            # Read error output
            for line in iter(process.stderr.readline, ''):
                print(f"Daemon Err: {line.strip()}")

            return False

        except Exception as e:
            print(f"Error starting Ruby server: {e}")
            return False

    def setup_osc_receiver(self):
        """Set up OSC receiver to handle incoming messages"""
        dispatcher = Dispatcher()

        # Register OSC message handlers
        dispatcher.map("/log/info", self._handle_log_info)
        dispatcher.map("/incoming/osc", self._handle_incoming_osc)
        dispatcher.map("/log/multi_message", self._handle_multi_message)
        dispatcher.map("/syntax_error", self._handle_syntax_error)
        dispatcher.map("/error", self._handle_error)

        # Create server in a separate thread
        try:
            self.osc_server = ThreadingOSCUDPServer(
                ("127.0.0.1", self.gui_listen_to_server_port), dispatcher)
            threading.Thread(target=self.osc_server.serve_forever, daemon=True).start()
            print(f"OSC server listening on port {self.gui_listen_to_server_port}")
        except Exception as e:
            print(f"Error setting up OSC server: {e}")

    def start_keep_alive(self):
        """Start keep-alive thread to maintain connection with daemon"""
        def send_keep_alive():
            while True:
                try:
                    if self.daemon_sender:
                        self.daemon_sender.send("/daemon/keep-alive", int(self.gui_uuid))
                    time.sleep(1)
                except Exception as e:
                    print(f"Error in keep-alive: {e}")
                    time.sleep(1)

        threading.Thread(target=send_keep_alive, daemon=True).start()

    def update_mixer_settings(self):
        """Update mixer settings based on configuration"""
        if self.config.get('invertStereo', False):
            self.mixer_invert_stereo()
        else:
            self.mixer_standard_stereo()

        if self.config.get('forceMono', False):
            self.mixer_mono_mode()
        else:
            self.mixer_stereo_mode()

    def run_code(self, code, offset=0):
        """Run Sonic Pi code"""
        if not self.server_started:
            if not self.start_server():
                print("Failed to start server")
                return False

        self.run_offset = offset

        # Add safe mode if configured
        if self.config.get('safeMode', False):
            code = 'use_arg_checks true #__nosave__ set by GUI user preferences.\n' + code

        if self.server_sender:
            self.server_sender.send("/run-code", int(self.gui_uuid), code)
            return True
        return False

    def stop_all_jobs(self):
        """Stop all running Sonic Pi jobs"""
        if self.server_sender:
            self.server_sender.send("/stop-all-jobs", int(self.gui_uuid))
            return True
        return False

    def start_recording(self):
        """Start audio recording"""
        if self.server_sender:
            self.server_sender.send("/start-recording", int(self.gui_uuid))
            return True
        return False

    def stop_recording(self):
        """Stop audio recording"""
        if self.server_sender:
            self.server_sender.send("/stop-recording", int(self.gui_uuid))
            return True
        return False

    def save_recording(self, path):
        """Save recorded audio to path"""
        if self.server_sender:
            self.server_sender.send("/save-recording", int(self.gui_uuid), path)
            return True
        return False

    def delete_recording(self):
        """Delete the current recording"""
        if self.server_sender:
            self.server_sender.send("/delete-recording", int(self.gui_uuid))
            return True
        return False

    def mixer_invert_stereo(self):
        """Invert stereo channels"""
        if self.server_sender:
            self.server_sender.send("/mixer-invert-stereo", int(self.gui_uuid))
            return True
        return False

    def mixer_standard_stereo(self):
        """Use standard stereo configuration"""
        if self.server_sender:
            self.server_sender.send("/mixer-standard-stereo", int(self.gui_uuid))
            return True
        return False

    def mixer_mono_mode(self):
        """Switch to mono mode"""
        if self.server_sender:
            self.server_sender.send("/mixer-mono-mode", int(self.gui_uuid))
            return True
        return False

    def mixer_stereo_mode(self):
        """Switch to stereo mode"""
        if self.server_sender:
            self.server_sender.send("/mixer-stereo-mode", int(self.gui_uuid))
            return True
        return False

    def shutdown(self):
        """Shut down the OSC server and connections"""
        if self.osc_server:
            self.osc_server.shutdown()

    # OSC message handlers
    def _handle_log_info(self, address, *args):
        """Handle log info messages"""
        message = args[1] if len(args) > 1 else ""

        # Check for run start/end messages
        import re
        match = re.search(r"(Completed|Starting) run (\d+)", message)
        if match:
            run_num = int(match.group(2))
            if match.group(1) == "Completed" and self.on_run_ended:
                self.on_run_ended(run_num)
            elif match.group(1) == "Starting" and self.on_run_started:
                self.on_run_started(run_num)

        if self.on_log:
            self.on_log(message)
        else:
            print(f"Log: {message}")

    def _handle_incoming_osc(self, address, *args):
        """Handle incoming OSC messages (cues)"""
        if len(args) >= 4:
            cue_name = args[2]
            cue_value = args[3]

            if self.on_cue:
                self.on_cue(cue_name, cue_value)
            else:
                print(f"Cue: {cue_name}: {cue_value}")

    def _handle_multi_message(self, address, *args):
        """Handle multi-part messages"""
        if len(args) >= 4:
            job_id = args[0]
            thread_name = args[1]
            runtime = args[2]
            count = args[3]

            message = f"{{run: {job_id}, time: {runtime}"
            if thread_name:
                message += f", thread: {thread_name}"
            message += "}"

            if self.on_log:
                self.on_log(message)
            else:
                print(message)

            for i in range(count):
                str_message = args[4 + 1 + 2 * i]
                if not str_message:
                    prefix = " |"
                elif i == count - 1:
                    prefix = " └─ "
                else:
                    prefix = " ├─ "

                for line in str_message.split("\n"):
                    if self.on_log:
                        self.on_log(prefix + line)
                    else:
                        print(prefix + line)

    def _handle_syntax_error(self, address, *args):
        """Handle syntax error messages"""
        if len(args) >= 4:
            job_id = args[0]
            desc = args[1]
            error_line = args[2]
            line = args[3] + self.run_offset

            error_message = f"Syntax error on job {job_id}: {desc}\nLine {line}: {error_line}"

            if self.on_syntax_error:
                self.on_syntax_error(job_id, desc, error_line, line)
            else:
                print(error_message)

    def _handle_error(self, address, *args):
        """Handle runtime error messages"""
        if len(args) >= 4:
            job_id = args[0]
            desc = args[1]
            backtrace = args[2]
            line = args[3] + self.run_offset

            error_message = f"Error on job {job_id}: {desc}\nLine {line}: {backtrace}"

            if self.on_error:
                self.on_error(job_id, desc, backtrace, line)
            else:
                print(error_message)

    # Callback setters
    def set_log_callback(self, callback):
        """Set callback for log messages"""
        self.on_log = callback

    def set_cue_callback(self, callback):
        """Set callback for cue messages"""
        self.on_cue = callback

    def set_error_callback(self, callback):
        """Set callback for error messages"""
        self.on_error = callback

    def set_syntax_error_callback(self, callback):
        """Set callback for syntax error messages"""
        self.on_syntax_error = callback

    def set_run_started_callback(self, callback):
        """Set callback for run started events"""
        self.on_run_started = callback

    def set_run_ended_callback(self, callback):
        """Set callback for run ended events"""
        self.on_run_ended = callback


# Example usage:
if __name__ == "__main__":
    # Configuration similar to what might come from VS Code settings
    config = {
        'sonicPiRootDirectory': '/Applications/Sonic Pi.app/Contents/Resources',
        'invertStereo': False,
        'forceMono': False,
        'safeMode': True,
        'logClearOnRun': True
    }

    wrapper = SonicPiWrapper(config)

    # Example callbacks
    def log_callback(message):
        print(f"LOG: {message}")

    def cue_callback(cue_name, cue_value):
        print(f"CUE: {cue_name} = {cue_value}")

    def run_started(run_id):
        print(f"Run started: {run_id}")

    def run_ended(run_id):
        print(f"Run ended: {run_id}")

    # Set callbacks
    wrapper.set_log_callback(log_callback)
    wrapper.set_cue_callback(cue_callback)
    wrapper.set_run_started_callback(run_started)
    wrapper.set_run_ended_callback(run_ended)

    # Usage example
    if wrapper.start_server():
        with open('/Users/gujun/Developer/Sonic_Pi_songs/backgrounds/rain/rain_01.pi', 'r') as file:
            print("Running Sonic Pi code...")
            # Read and run the code from the file
            code = file.read()
        wrapper.run_code(code)
        # Keep script running to receive messages
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            wrapper.shutdown()
            print("\nShutting down...")
