import pymysql
pymysql.install_as_MySQLdb()

# Django 6.0 requires mysqlclient >= 2.2.1, but PyMySQL reports as 1.4.6
# Override the version to bypass the check
pymysql.version_info = (2, 2, 1, 'final', 0)
