const express = require('express');
const admin = require('firebase-admin');
const cors = require('cors');
const multer = require('multer');
const upload = multer(); // For handling multipart/form-data

// Initialize Firebase Admin SDK
const serviceAccount = require('./serviceAccountKey.json');

admin.initializeApp({
  credential: admin.credential.cert(serviceAccount),
});

const auth = admin.auth();

const app = express();
app.use(cors());
app.use(express.json());

// Middleware to verify Firebase ID Token
async function verifyFirebaseToken(req, res, next) {
  try {
    const authHeader = req.headers.authorization || '';
    const idToken = authHeader.startsWith('Bearer ')
      ? authHeader.split('Bearer ')[1]
      : null;

    if (!idToken) {
      return res.status(401).json({ error: 'No Firebase ID token provided' });
    }

    const decodedToken = await auth.verifyIdToken(idToken);
    req.user = decodedToken; // Save user info in request
    next();
  } catch (error) {
    console.error('Error verifying Firebase ID token:', error);
    return res.status(401).json({ error: 'Unauthorized: Invalid token' });
  }
}

// Route to handle resume analysis
app.post('/analyze', verifyFirebaseToken, upload.fields([
  { name: 'resume', maxCount: 1 },
  { name: 'job_description', maxCount: 1 },
]), async (req, res) => {
  try {
    // Access user info verified from token
    console.log('User UID:', req.user.uid);
    console.log('User Email:', req.user.email);

    // Access files
    const resumeFile = req.files['resume'] ? req.files['resume'][0] : null;
    const jobDescFile = req.files['job_description'] ? req.files['job_description'][0] : null;
    const mode = req.body.mode;
    const recruiterEmail = req.body.recruiterEmail;
    const jobDescription = req.body.jobDescription;

    // Simple mock response - replace with your analysis logic
    const analysisResult = {
      strengths: ['Good skills in React', 'Strong project experience'],
      areas_of_improvement: ['Add more backend projects', 'Improve formatting'],
      recommended_jobs: ['Frontend Developer', 'React Engineer'],
      general_feedback: 'Overall, your resume looks solid!',
    };

    return res.json({ feedback: analysisResult });
  } catch (error) {
    console.error('Error processing /analyze:', error);
    return res.status(500).json({ error: 'Internal Server Error' });
  }
});

const PORT = process.env.PORT || 5000;
app.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
