import os
import pty
import sys
import tty
import termios
import select

def main():
    # Fork a child process with its own pseudo-terminal
    pid, master_fd = pty.fork()

    if pid == 0:
        # CHILD process -> replace with Zsh
        #
        # -i = interactive
        # (You might also want -l for a login shell, or omit flags if you prefer.)
        #
        # Not passing --no-rcs or --no-profile means:
        #   Zsh will load your ~/.zshrc, compinit, etc.
        #   This ensures all your normal Zsh completions and plugins are available.
        #
        os.execlp("zsh", "zsh", "-i")
    else:
        # PARENT process -> Relay I/O between your "mock terminal" and Zsh
        old_tty = termios.tcgetattr(sys.stdin)
        try:
            # Use cbreak mode (instead of raw) to preserve some echo behavior
            tty.setcbreak(sys.stdin.fileno())

            while True:
                # Wait for input from user or from the child (Zsh)
                ready_fds, _, _ = select.select([sys.stdin, master_fd], [], [])

                if sys.stdin in ready_fds:
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break  # End of input (e.g. Ctrl+D)
                    os.write(master_fd, data)

                if master_fd in ready_fds:
                    data = os.read(master_fd, 1024)
                    if not data:
                        break  # Zsh exited
                    os.write(sys.stdout.fileno(), data)

        finally:
            # Restore your terminal’s original settings
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)

if __name__ == "__main__":
    main()
