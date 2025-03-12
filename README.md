# AI Terminal

## Description

This is a terminal that uses AI to help you write code, execute commands, and more.

## Requirements

- Python 3.10+
- OpenAI API key
- ZSH (MUST BE INSTALLED)

## Usage

```bash
python ai_terminal.py
```

## Features
Use it like a normal terminal, but with AI help.

when you need ai help, just type `ai <your question>` and press enter.

ai can read your command history and output, so it can help you write code, execute commands, and more.

![usage](./images/usage.png)

## Limitations

right now AI cannot directly execute commands, it will only return the command that you can copy and paste into your terminal.
when hit Ctrl+C, the terminal (not the command) will exit.

## TODO

- [ ] Add a way to execute commands directly from the AI.
- [ ] Add a way to handle user interaction commands (e.g. `git push`).
- [ ] handle Ctrl+C gracefully.
