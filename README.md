# PVSiteAPI
<!-- ALL-CONTRIBUTORS-BADGE:START - Do not remove or modify this section -->
[![All Contributors](https://img.shields.io/badge/all_contributors-4-orange.svg?style=flat-square)](#contributors-)
<!-- ALL-CONTRIBUTORS-BADGE:END -->
Site specific API for SBRI project


## Setup and Run

### [Install poetry][p]

### Install python dependencies

    poetry install

### Start the API using uvicorn

    # Make a `.env` file and edit its content.
    cp -n .env.dist .env
    # Alternatively, you can set all the environment variables manually.

    # Start the service
    poetry run uvicorn pv_site_api.main:app --reload


## Running the tests

    poetry run pytest tests


## Coding style

Format the code *in place*

    make format

Verify that the code satisfies the style

    make lint


## Contributors ✨

Thanks goes to these wonderful people ([emoji key](https://allcontributors.org/docs/en/emoji-key)):

<!-- ALL-CONTRIBUTORS-LIST:START - Do not remove or modify this section -->
<!-- prettier-ignore-start -->
<!-- markdownlint-disable -->
<table>
  <tbody>
    <tr>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/peterdudfield"><img src="https://avatars.githubusercontent.com/u/34686298?v=4?s=100" width="100px;" alt="Peter Dudfield"/><br /><sub><b>Peter Dudfield</b></sub></a><br /><a href="https://github.com/openclimatefix/pv-site-api/commits?author=peterdudfield" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/rachel-labri-tipton"><img src="https://avatars.githubusercontent.com/u/86949265?v=4?s=100" width="100px;" alt="rachel tipton"/><br /><sub><b>rachel tipton</b></sub></a><br /><a href="https://github.com/openclimatefix/pv-site-api/commits?author=rachel-labri-tipton" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="https://github.com/ericcccsliu"><img src="https://avatars.githubusercontent.com/u/62641231?v=4?s=100" width="100px;" alt="Eric Liu"/><br /><sub><b>Eric Liu</b></sub></a><br /><a href="https://github.com/openclimatefix/pv-site-api/commits?author=ericcccsliu" title="Code">💻</a></td>
      <td align="center" valign="top" width="14.28%"><a href="http://lefun.fun"><img src="https://avatars.githubusercontent.com/u/1105380?v=4?s=100" width="100px;" alt="Simon Lemieux"/><br /><sub><b>Simon Lemieux</b></sub></a><br /><a href="https://github.com/openclimatefix/pv-site-api/commits?author=simlmx" title="Code">💻</a></td>
    </tr>
  </tbody>
</table>

<!-- markdownlint-restore -->
<!-- prettier-ignore-end -->

<!-- ALL-CONTRIBUTORS-LIST:END -->

This project follows the [all-contributors](https://github.com/all-contributors/all-contributors) specification. Contributions of any kind welcome!

[p]: https://python-poetry.org/docs/#installation
