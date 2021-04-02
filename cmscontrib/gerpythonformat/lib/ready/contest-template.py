description("~")
timezone("Europe/Berlin")
load_template("lg", short_name="Dummywettbewerb")
allow_usual_languages()

user_group("main", start=time("2000-01-01 00:00:00"),
           stop=time("2100-01-01 00:00:00"))
test_user(user("testcontesttestuser", "secret", "Testcontest", "Testuser"))
