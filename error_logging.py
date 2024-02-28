import logging
from botocore.exceptions import ClientError, NoCredentialsError, ParamValidationError

logging.basicConfig(filename='devops.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ANSI Colour Codes
COLOURS = {
    "info": "\033[92m",  # Green
    "error": "\033[91m",  # Red
    "warning": "\033[93m",  # Yellow
    "reset": "\033[0m",  # Reset to default colour
}

def error_handler(func):
    """
    A decorator that handles common AWS errors and exceptions.
    """
    def _Decorator(*args, **kwargs):
        log(f">> Running function {func.__name__} <<", "debug")
        try:
            return func(*args, **kwargs)
        except NoCredentialsError:
            log("No AWS credentials found. Please configure your credentials.", "error")
            exit(1)
        except ClientError as e:
            log(f"An error occurred: {e}", "error")
        except ParamValidationError as e:
            log(f"Invalid parameters: {e}", "error")
        except TypeError as e:
            log(f"Invalid type: {e}", "error")
        except ImportError as e:
            log(f"Import error: {e}", "error")
        except Exception as e:
            log(f"An error occurred: {e}", "error")
        
        log(f">> Finished function {func.__name__} <<", "debug")
    return _Decorator

def log(message, level="info"):
    """
    Logs a message to the console and a log file.

    Parameters:
    - message: The message to log.
    - level: The log level (info, error, warning).
    """
    if not level == "debug":
        colour = COLOURS.get(level, COLOURS["reset"])
        coloured_message = f"{colour}{message}{COLOURS['reset']}"
        print(coloured_message)
        print("-------------------")

    if level == "info":
        logging.info(message)
    elif level == "error":
        logging.error(message)
    elif level == "warning":
        logging.warning(message)
    elif level == "debug":
        logging.info(message)