#!/bin/sh
cd /var/www/html/laravel-realworld-example-app
mv .env ../.env
sudo git pull
mv ../.env .env