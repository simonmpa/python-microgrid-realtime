![image](https://media.discordapp.net/attachments/311213361125916672/1355122972750512228/gaylol.jpg?ex=67e7c81d&is=67e6769d&hm=a4bbb0ed48ed36ae2498c86dd3bce700b7a9b66f473a4fcf362fc09b69f26983&=&format=webp)

# How to run the simulation

Before getting started, create the database by running the following command:

```bash
python src/database.py
```

To run the simulation, you will need two terminals. Open the first terminal in the *python-microgrid-realtime* directory and run the following command:

```bash
flask --app src/api run
```

Likewise, open the second terminal in the *python-microgrid-realtime* directory and run the following command:

```bash
python src/app.py
```