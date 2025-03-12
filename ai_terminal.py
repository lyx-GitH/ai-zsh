import os
import pty
import sys
import tty
import termios
import select
import re
import openai
import dotenv
from datetime import datetime

dotenv.load_dotenv()

history = []
MAX_HISTORY_SIZE = 100

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY is not set")

def is_ai_command(command: str) -> tuple[bool, str]:
    """
    Check if a command is an AI command and extract the prompt if it exists.
    
    Args:
        command: Input command string
    
    Returns:
        tuple of (is_ai_command, prompt)
        - is_ai_command: True if command is exactly 'ai' or starts with 'ai '
        - prompt: The prompt text after 'ai', or empty string if just 'ai'
    """
    # Pattern matches:
    # - exactly 'ai'
    # - 'ai' followed by space and optional words
    pattern = re.compile(r'^ai(?:\s+(.+))?$')
    
    # First check if it's exactly 'ai' or starts with 'ai '
    if not (command == 'ai' or command.startswith('ai ')):
        return (False, '')
    
    match = pattern.match(command)
    if match:
        prompt = match.group(1) or ''
        return (True, prompt.strip())
    
    return (False, '')

def handle_ai_query(history: list, prompt: str = None, old_tty=None) -> None:
    """
    Handle AI interactions, either with a specific prompt or in conversation mode.
    
    Args:
        history: List of previous commands and their outputs
        prompt: Optional prompt string. If None, enter conversation mode
        old_tty: Original terminal settings to restore for interactive mode
    """
    # Initialize OpenAI client
    client = openai.OpenAI()
    model = "gpt-4o"
    
    # Prepare context from history
    context = "Previous commands and outputs:\n"
    for cmd in history[-10:]:
        context += str(cmd)
    
    if prompt:
        # Single question mode
        messages = [
            {"role": "system", "content": "You are a helpful terminal assistant. You have access to the command history and outputs. "},
            {"role": "user", "content": f"{context}\nQuestion: {prompt}"}
        ]
        
        # Use streaming for character-by-character output
        print("\nAI: ", end="", flush=True)
        full_response = ""
        stream = client.chat.completions.create(
            model=model,
            messages=messages,
            stream=True  # Enable streaming
        )
        
        for chunk in stream:
            if chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                print(content, end="", flush=True)
                full_response += content
        print("\n")
        
        command = {
            "user_input": prompt,
            "ai_response": full_response,
        }
        add_to_history(command)
    else:
        # Interactive conversation mode
        print("Entering AI conversation mode (type 'exit' to leave)")
        messages = [
            {"role": "system", "content": "You are a helpful terminal assistant. You have access to the command history and outputs."},
            {"role": "user", "content": context}
        ]
        
        # Restore normal terminal mode for input
        if old_tty:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)
        
        try:
            while True:
                user_input = input(f"Ask {model}: ")
                if user_input.lower() == 'exit':
                    break
                    
                messages.append({"role": "user", "content": user_input})
                
                try:
                    print("\nAI: ", end="", flush=True)
                    full_response = ""
                    stream = client.chat.completions.create(
                        model=model,
                        messages=messages,
                        stream=True  # Enable streaming
                    )
                    
                    for chunk in stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            print(content, end="", flush=True)
                            full_response += content
                    print("\n")
                    
                    messages.append({"role": "assistant", "content": full_response})
                except Exception as e:
                    print(f"Error calling OpenAI API: {e}")
                    break
        finally:
            # Restore raw mode before returning to main loop
            if old_tty:
                tty.setcbreak(sys.stdin.fileno())

def execute(master_fd: int, command: str, timeout: float = 0.1) -> str:
    """
    Execute a command in the remote shell and return its output.
    
    Args:
        master_fd: File descriptor for the master end of the PTY
        command: Command string to execute
        timeout: Timeout in seconds for reading output
    
    Returns:
        The command output as a string
    """
    # Add newline if not present
    if not command.endswith('\n'):
        command += '\n'
    
    # Send command to shell
    os.write(master_fd, command.encode('utf-8'))
    
    # Read the response
    output_buffer = bytearray()
    while True:
        ready, _, _ = select.select([master_fd], [], [], timeout)
        if not ready:
            break
            
        data = os.read(master_fd, 1024)
        if not data:
            break
            
        output_buffer.extend(data)
        if b'%' in data:  # Wait for prompt to ensure command completed
            break
    
    try:
        raw_output = output_buffer.decode('utf-8')
        cleaned_output = clean_terminal_output(raw_output)
        # print(f"{cleaned_output=}")
        pattern = re.compile(r'1;(\w+)\s+(.+?)(?=%)')
        match = pattern.search(cleaned_output)
        if match:
            command = match.group(1).strip()  # First word after "1;"
            output = match.group(2).strip()   # Rest of the content until "%"
            return (command, output)
        else:
            print(f"failed to find match for {raw_output=}")
            return ('', '')
        
        
    except UnicodeDecodeError:
        return ""

def add_to_history(command: tuple[str, str]):
    history.append(command)
    if len(history) > MAX_HISTORY_SIZE:
        history.pop(0)





def clean_terminal_output(raw_output: str) -> str:
    """
    Clean raw terminal output by removing ANSI escapes and control characters.
    
    Args:
        raw_output: Raw terminal output string
    
    Returns:
        Cleaned output string
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
    
    return cleaned_output

def parse_terminal_output(raw_output: str) -> tuple[str, str]:
    """
    Parse raw terminal output and extract command-output pairs.
    
    Args:
        raw_output: Raw terminal output string
    
    Returns:
        List of tuples containing (command, output)
    """
    cleaned_output = clean_terminal_output(raw_output)
    # print(f"{cleaned_output=}")
    
    start = cleaned_output.find("2;")
    end = cleaned_output.find("1;")
    input_command = cleaned_output[start:end].split(";")[1].rstrip()
    first_token = input_command.split(" ")[0]
    output_header = "1;" + first_token
    
    # print(f"{input_command=}")
    # print(f"{first_token=}")
    print(f"{cleaned_output=}")
    print(f"{output_header=}")
    pattern = re.compile(r'1;(\w+)\s+(.+?)(?=%|$)')
    match = pattern.search(cleaned_output)
    
    if match:
        command = match.group(1).strip()  # First word after "1;"
        output = match.group(2).strip()   # Rest of the content
        return (input_command, output)
    else:
        print(f"failed to find match for {cleaned_output=}")
        return (input_command, "")
   

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
            execute(master_fd, "clear")
            execute(master_fd, "echo 'Welcome to the AI terminal!'")

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
                                    last_ret_value = execute(master_fd, "echo $?")
                                    pwd_res = execute(master_fd, "pwd")
                                    command = {
                                        "input": parsed_output[0],
                                        "output": parsed_output[1],
                                        "pwd": pwd_res[1],
                                        "last_ret_value": last_ret_value[1],
                                    }
                                    # print(command)
                                    # add_to_history(parsed_output)
                                    is_ai, prompt = is_ai_command(command["input"])
                                    
                                    if is_ai:
                                        handle_ai_query(history, prompt, old_tty)
                                    else:
                                        add_to_history(command)
                                        print(f"Add to history: {command=}")
                                    # _ = input("press any key to continue")
                                    
                                    last_command = None
                                    
                                    
                                    print(f"(You are in ai terminal mode)")
                                output_buffer.clear()
                    except UnicodeDecodeError:
                        pass
                    
                    os.write(sys.stdout.fileno(), data)

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

if __name__ == "__main__":
    main()
