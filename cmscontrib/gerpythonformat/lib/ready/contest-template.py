description("~")
timezone("Europe/Berlin")
contest.lg = "Dummywettbewerb"

from cmscontrib.gerpythonformat.templates.lg.LgTemplate import LgTemplate
LgTemplate(contest)

user_group("main", start=time("2000-01-01 00:00:00"),
           stop=time("2100-01-01 00:00:00"))
test_user(user("testcontesttestuser", "secret", "Testcontest", "Testuser"))
