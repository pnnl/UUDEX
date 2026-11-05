## Setup

------------

#### Requirements
These instructions assume the following:
- The UUDEX server is being installed onto a Linux host.  All Linux distributions are supported.
- A Postgres database instance is available.  Version 11 or above.
- A RabbitMQ server has been installed and is available.  Version 3.8 or above.
- Python 3 is installed.  The application was developed against Python 3.6 but will work with 3.6 or above.
<br />

#### 1. Create the UUDEX repository
- Ensure the Postgres pg_hba.conf file allows md5 authenticated logins from localhost. See https://www.postgresql.org/docs/11/auth-pg-hba-conf.html
- Create a new Postgres database for the UUDEX repository.  For example, a database named *uudex*
- Create a new database user for the UUDEX application to use
> For example: CREATE ROLE uudex_user WITH
  LOGIN
  SUPERUSER
  INHERIT
  NOCREATEDB
  NOCREATEROLE
  NOREPLICATION
   PASSWORD 'password';

- A pg_dump file is provided in the Gitbub repository (under database directory) that will create all database objects and create some sample data.  Refer [here](https://www.postgresql.org/docs/9.1/backup-dump.html "here") on how to restore a Postgres dump file.  
<br/>

#### 2. Configure RabbitMQ
- Create a user in RabbitMQ for use by UUDEX.  This user should be an administrator and use basic authentication.  The rabbitmqctl tool can be used for this.  [Reference](https://www.zerto.com/myzerto/knowledge-base/how-to-create-rabbitmq-user/ "Reference")

- The RabbitMQ managment plugin is required.  The plugin is already included in the RabbbitMQ install and just needs to be enabled.

`$ rabbitmq-plugins enable rabbitmq_management`

<br/>

#### 3. Install the UUDEX Server
- Copy the code under the Github repository src directory to a new install directory on your Linux server.  i.e., /apps/uudex

- In your newly created install directory, create a new Python virtual environment

`$ cd [new install directory]`

`$ python -m venv .`

`$ . bin/activate`

- Install the required standard packages for UUDEX

`$ pip3 install -r requirements.txt`

- Install the gunicorn server package

`$ pip3 install gunicorn`

- Setup log directory.   Run the following commands from the UUDEX directory, created above.  i.e., /apps/uudex

`$ cd [new install directory]`

`$ mkdir logs/`

`$ touch logs/uudex.log`

<br/>

#### 4. Configure the UUDEX Server
- The Github repository has a directory named 'mock_ssl_certs'.  This contains server SSL certificates that can be used to get the UUDEX up and running.
- Edit the gunicorn.conf.py file in the root install directory.  The only parameters you should have to change in this fille are the paths to the certicate files.  Update the three parameters to your local paths. * **Note**: The parameter 'bind' in this file contains the port the UUDEX server will listen on.  For this multi-site demo we will use port 3546.*

- In the config directory, edit the setting.py file.  If needed, change the parameters SQLALCHEMY_DATABASE_URI and MESSAGE_BROKER_URL to point to a remote Postgress database or remote RabbitMQ message broker, respectively.  The default for is localhost.  The applicable parameters are under the 'class BaseConfig()' and 'class GunicornConfig(BaseConfig)' sections.  Use the usernames and passwords defined in the steps above.  ***

- Finally, start the UUDEX server by running the script start_uudex.sh  The server log is stored under the log directoy.

<br/>

#### 5. Test the UUDEX Server
- You can test the server with the following curl command.  The test client certificate and key file can be found under the 'mock_ssl_certs/client' directory.
> curl 'https://localhost:3546/v1/uudex/parent-participant' --header "Content-Type: application/json" \
--key [path to client key file] \
--cert [path to client cer file] \
--cacert [path to ca file]

For example:
> curl 'https://localhost:3546/v1/uudex/parent-participant' --header "Content-Type: application/json" \
--key uudex/ssl/client/client.key \
--cert uudex/ssl/client/client.crt \
--cacert uudex/ssl/ca/ca.pem

If successful, the output should resemble:

```json
{
    "participant_uuid": "feea5be2-aeb0-4456-b3f4-cefcb521f8ae",
    "participant_short_name": "ICCP_Demo_1",
    "participant_long_name": "Utility 1",
    "description": "ICCP Demo-Consumer",
    "root_org_sw": "Y",
    "active_sw": "Y",
    "create_datetime": "2020-07-29T20:18:07",
    "contacts": []
}
```

