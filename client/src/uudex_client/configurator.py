import configparser
import logging

#
# Note: This code is not auto generated
#

"""
  Helper function that sets the UUDEX client configuration information from an ini file.
  

  configuration:  The uudex_client.Configuration object to be set.   

  connection:  The connection name to use, which is a section name in an ini file that contains the attributes for the 
               connection.  i.e., pnnl or mitre
  
  The Attributes in the ini file for each "connection" section consist of:
  host = the hostname of the server the UUDEX server resides on (REQUIRED)
  ssl_ca_cert = The CA cert file the UUDEX client should use (REQUIRED)
  cert_file = The user certificate file the UUDEX client should use (REQUIRED)
  key_file = The user certificate private key file the UUDEX client should use (REQUIRED)
  log_level = The desired log level (OPTIONAL)
    
  config_file: The path and file name to the ini file.  This is optional and defaults to looking
            in the current directory for a file named 'uudex_broker_client.ini'

  Returns: A dictionary consisting of the attributes above.  log_level value is the Python numeric log level and  
           defaults to 20 (INFO) if it's not defined in ini file.  Can be used with a call 
           to logger.setLevel(numeric_level) 
 
"""
def set_values(configuration, connection, config_file=None):
    config = configparser.RawConfigParser()
    config_file = config_file if config_file is not None else 'uudex_client.ini'
    file = config.read(config_file)
    if not file:
        raise FileNotFoundError(f"config file {config_file} not found")

    if not config.has_section(connection):
        raise configparser.NoSectionError(f"'{connection}' section missing from config file")

    # this is verbose code for these checks but want it to return friendly errors
    if not config.has_option(connection, "host"):
        raise configparser.NoOptionError("host setting required in config file")
    if not config.has_option(connection, "ssl_ca_cert"):
        raise configparser.NoOptionError("ssl_ca_cert setting required in config file")
    if not config.has_option(connection, "cert_file"):
        raise configparser.NoOptionError("cert_file setting required in config file")
    if not config.has_option(connection, "key_file"):
        raise configparser.NoOptionError("key_file setting required in config file")

    config_values = dict()
    loglevel = config.get(connection, 'log_level') if config.has_option(connection, "log_level") else "INFO"
    numeric_level = getattr(logging, loglevel.upper(), None)
    config_values['log_level'] = numeric_level

    config_values['host'] = config.get(connection, 'host')
    config_values['ssl_ca_cert'] = config.get(connection, 'ssl_ca_cert')
    config_values['cert_file'] = config.get(connection, 'cert_file')
    config_values['key_file'] = config.get(connection, 'key_file')

    configuration.host = f"https://{config_values['host']}/v1/uudex"
    configuration.ssl_ca_cert = config_values['ssl_ca_cert']
    configuration.cert_file = config_values['cert_file']
    configuration.key_file = config_values['key_file']
    configuration.verify_ssl = True  # force host validation
    configuration.debug = True if loglevel == "DEBUG" else False

    return config_values
