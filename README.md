# 📚 bookshelf 📚
a program that creates an image to display the spines of the books you've read

I've included a default bookshelf image and a few spines in the "example" folder to demonstrate how the program works. But you can feed it any bookshelf image, its dimensions, and a bunch of book spine files and their dimensions, and this program will create an image for you.
At some point in the future, I might make a website that does all this for you. Maybe we'll build a beautiful book spine API the whole world can use 🌎 

### How to Run CockroachDB Locally
- install cockroachDB locally (https://www.cockroachlabs.com/docs/v25.2/install-cockroachdb-windows)

In terminal A, run
cockroach start --insecure --store=node1 --listen-addr=localhost:26257 --http-addr=localhost:8080 --join=localhost:26257

To initialize the DB (if first time runnning) run

cockroach init --insecure --host=localhost:26257

Now you can run a sql client to connect to your local database by running
cockroach sql --insecure --host=localhost:26257

You'll also need to set some environment variables:
DATABASE_URL=localhost:26257 // im not sure on this URL, need to test. Also, might be good to rename the environment variable so its more specific to this project
SSLROOTCRT // (rename)  not sure if necessary. maybe could be used to denote that if null this isn't a prod server?


### Local AWS API Gateway Emulation
Look into AWS SAM CLI