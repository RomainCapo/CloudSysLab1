#!/bin/sh
cd /var/www/html
sudo git clone https://github.com/RomainCapo/laravel-realworld-example-app.git
cd laravel-realworld-example-app
sudo cp /home/romain_capocasale99/.env /var/www/html/laravel-realworld-example-app 
sudo composer install --ignore-platform-reqs 
sudo php artisan key:generate 
sudo php artisan jwt:generate 
sudo php artisan migrate --force
sudo php artisan db:seed --force 
sudo php artisan config:clear 
sudo composer dump-autoload