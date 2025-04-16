import configparser

# Read settings from settings.ini file
config = configparser.ConfigParser()
config.read('config/settings.ini')

def get_download_liked():
    return config['SETTINGS'].getboolean('DOWNLOAD_LIKED', fallback=True)

def get_update_frequency():
    return config['SETTINGS'].get('UPDATE_FREQUENCY', fallback='daily')

def get_download_location():
    return config['SETTINGS'].get('DOWNLOAD_LOCATION', fallback='data/')

def update_settings(section, option, value):
    config.set(section, option, value)
    with open('config/settings.ini', 'w') as configfile:
        config.write(configfile)
