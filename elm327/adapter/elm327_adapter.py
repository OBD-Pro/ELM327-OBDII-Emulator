from elm327.adapter.replies import NO_DATA, UNKNOWN_COMMAND


class Elm327Adapter:
    def __init__(self, settings, at_commands, obd_services, formatter):
        self.settings = settings
        self.at_commands = at_commands
        self.obd_services = obd_services
        self.formatter = formatter

    def handle_line(self, line):
        command = line.replace(" ", "").upper()
        if command.startswith("AT"):
            return self.at_commands.handle(command)
        return self._format_service_reply(self.obd_services.handle(command))

    def _format_service_reply(self, reply):
        if not reply or reply in (NO_DATA, UNKNOWN_COMMAND):
            return reply
        if not self.settings.accepts(int(self.settings.response_id, 16)):
            return NO_DATA
        return self.formatter.format(reply)
