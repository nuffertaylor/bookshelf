const { Client } = require("pg");

class Cockroach_Dao {
  constructor(db_url) {
    this.client = new Client(process.env.DATABASE_URL);
  }
  
}


(async () => {
  await client.connect();
  try {
    const results = await client.query("SELECT NOW()");
    console.log(results);
  } catch (err) {
    console.error("error executing query:", err);
  } finally {
    client.end();
  }
})();