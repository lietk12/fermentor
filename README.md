# fermenter
fermenter is the codebase to control a simple Arduino-driven fermenter and provide a web interface. This was done by Ethan Li and Jessica Lam for the project extension for BIOE 123 ("Optics and Devices Lab") at Stanford University.

## Dependencies
- python 2: required by Flask-SocketIO
- [Flask](http://flask.pocoo.org/)
- [Flask-SocketIO](https://github.com/miguelgrinberg/Flask-SocketIO) for real-time communication between a web browser and the server
- [Python-Arduino-Command-API](https://github.com/thearn/Python-Arduino-Command-API) for Arduino interfacing
