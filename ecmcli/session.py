"""
Interactive session for ECM.
"""

import shellish


class ECMSession(shellish.Session):

    command_error_verbosity = 'pretty'
    default_prompt_format = r': \033[7m{user}\033[0m@{site} ;\n:;'
    intro = '\n'.join([
        'Welcome to the ECM shell.',
        'Type "help" or "?" to list commands and "exit" to quit.'
    ])

    def prompt_info(self):
        info = super().prompt_info()
        info.update({
            "user": self.root_command.api.ident['user']['username'],
            "site": self.root_command.api.site.split('//', 1)[1]
        })
        return info
