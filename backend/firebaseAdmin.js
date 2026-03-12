const admin = require('firebase-admin');

// Replace './serviceAccountKey.json' with the path to your Firebase service account key JSON file
const serviceAccount = require('./serviceAccountKey.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const auth = admin.auth();
module.exports = auth;