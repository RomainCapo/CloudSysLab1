#!/bin/sh
cd /home/romain_capocasale99
git clone https://github.com/RomainCapo/vue-realworld-example-app.git
cd vue-realworld-example-app
npm install -g editorconfig
yarn install
yarn serve