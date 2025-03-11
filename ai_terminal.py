import os
import pty
import sys
import tty
import termios
import select
import re

history = []
MAX_HISTORY_SIZE = 100

def add_to_history(command: tuple[str, str]):
    history.append(command)
    if len(history) > MAX_HISTORY_SIZE:
        history.pop(0)



def parse_terminal_output(raw_output: str) -> tuple[str, str]:
    """
    Parse raw terminal output and extract command-output pairs.
    
    Args:
        raw_output: Raw terminal output string
    
    Returns:
        List of tuples containing (command, output)
    """
    # Pattern to remove ANSI escape sequences
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    # Pattern to remove control characters
    control_chars = re.compile(r'[\x00-\x1F\x7F-\x9F\r\n\x07>]+')
    
    # Clean the output in multiple steps
    cleaned_output = raw_output
    cleaned_output = ansi_escape.sub('', cleaned_output)  # Remove ANSI escapes
    cleaned_output = control_chars.sub(' ', cleaned_output)  # Replace control chars with space
    cleaned_output = re.sub(r'\s+', ' ', cleaned_output)  # Normalize whitespace
    cleaned_output = cleaned_output.strip()
    
    
    
    start = cleaned_output.find("2;")
    end = cleaned_output.find("1;")
    input_command = cleaned_output[start:end].split(";")[1].rstrip()
    first_token = input_command.split(" ")[0]
    
    # print(f"{input_command=}")
    # print(f"{first_token=}")
    
    output = cleaned_output[end:].split(first_token)[1].rstrip()
    # print(f"{output=}")
    return (input_command, output)

def main():
    # Fork a child process with its own pseudo-terminal
    pid, master_fd = pty.fork()

    if pid == 0:
        # Child process
        os.execlp("zsh", "zsh", "-i")
    else:
        # Parent process
        old_tty = termios.tcgetattr(sys.stdin)
        command_buffer = bytearray()
        output_buffer = bytearray()
        last_command = None
        
        # Pattern to remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        
        try:
            tty.setcbreak(sys.stdin.fileno())

            while True:
                ready_fds, _, _ = select.select([sys.stdin, master_fd], [], [])

                if sys.stdin in ready_fds:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break
                    
                    command_buffer.extend(data)
                    if b'\n' in data or b'\r' in data:
                        try:
                            command = command_buffer.decode('utf-8').strip()
                            if command:
                                # print("\nCommand entered:", command)
                                last_command = command
                                output_buffer.clear()
                        except UnicodeDecodeError:
                            pass
                        command_buffer.clear()
                    
                    os.write(master_fd, data)

                if master_fd in ready_fds:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break
                    
                    output_buffer.extend(data)
                    
                    try:
                        output = output_buffer.decode('utf-8')
                        # Look for the pattern: command output followed by a prompt
                        if '%' in output and last_command:
                            parts = output.split('%')
                            if len(parts) >= 2:
                                # Clean the output
                                cleaned_output = ansi_escape.sub('', parts[0])
                                # Remove the echoed command
                                cleaned_output = re.sub(f'^.*{last_command}.*\n', '', cleaned_output)
                                cleaned_output = cleaned_output.strip()
                                
                                if cleaned_output and not cleaned_output.isspace():
                                    # print("Command output:", cleaned_output)
                                    parsed_output = parse_terminal_output(cleaned_output)
                                    print(parsed_output)
                                    add_to_history(parsed_output)
                                    last_command = None
                                output_buffer.clear()
                    except UnicodeDecodeError:
                        pass
                    
                    os.write(sys.stdout.fileno(), data)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

if __name__ == "__main__":
    main()
