#SimpleSyncthing

Client permettant de récupérer les fichiers présents sur un dépôt syncthing distant en lecture seule.

##Prérequis

Le programme se trouve dnas le dossier programme. Il faut choisir un dossier de destination existant mais vide présent dans le repertoire courant. Il faut avoir dans le répertoire courant un fichier cert.pem et key.pem reconnus par le serveur syncthing. Le programme se lance avec la commande : python3 SimpleSyncthing.py -f <dossier>

##Exécution

Des retours seront affichés dans le terminal pour connaître l'état actuel du processus. Le programme une fois lancé télécharge tout le contenu des deux partages facile et moins_facile dans le répertoire donné en argument. Une fois fait, le programme continue à tourner, pingant régulièrement le serveur distant.
