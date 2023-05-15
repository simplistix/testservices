from socket import create_connection, error as socket_error
from time import sleep


def wait_for_server(
        port: int, address: str = '127.0.0.1', timeout: float = 5, poll_frequency: float = 0.05
) -> None:
    assert port is not None, 'port may not be None'
    waited: float = 0
    while waited < timeout:
        try:
            create_connection((address, port))
        except socket_error as e:
            if 'connection refused' not in str(e).lower():
                raise
        else:
            return
        sleep(poll_frequency)
        waited += poll_frequency
    raise TimeoutError('server on {}:{} did not start within {}s'.format(
        address, port, timeout
    ))
