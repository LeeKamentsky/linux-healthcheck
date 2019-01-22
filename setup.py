from setuptools import setup

setup(name="linux_healthcheck",
      version="1.0.0",
      description="Lee's linux system healthcheck",
      author="Lee Kamentsky",
      packages=["linux_healthcheck"],
      entry_points=dict(console_scripts=[
          'linux-healthcheck-new-credentials='
          'linux_healthcheck.main:write_credentials_file',
          'linux-healthcheck-new-counter='
          'linux_healthcheck.main:new_counter',
          'linux-healthcheck=linux_healthcheck.main:main'
      ]),
      url="http://github.com/LeeKamentsky/linux_healthcheck",
      license="MIT")
