const auth = require('./firebaseAdmin');

async function addUserOrUpdate(email, password) {
  try {
    // Check if the user already exists
    const existingUser = await auth.getUserByEmail(email);
    console.log('User already exists. Updating password...');
    console.log(`Updating password for user: ${existingUser.uid} with password: ${password}`); // Debugging log
    await auth.updateUser(existingUser.uid, { password: password });
    console.log('Password updated successfully for user:', existingUser.uid);
  } catch (error) {
    if (error.code === 'auth/user-not-found') {
      // If the user does not exist, create a new user
      try {
        const newUser = await auth.createUser({
          email: email,
          password: password,
        });
        console.log('User created successfully:', newUser.uid);
      } catch (createError) {
        console.error('Error creating user:', createError.message);
      }
    } else {
      console.error('Error checking user existence:', error.message);
    }
  }
}

// Call the function with the desired email and password
addUserOrUpdate('0105cd221021@oriental.ac.in', 'your-new-strong-password');