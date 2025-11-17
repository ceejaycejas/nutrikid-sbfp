# Gmail Email Setup Instructions

## ⚠️ IMPORTANT: Use Gmail App Password

Gmail **does NOT allow** using your regular account password for SMTP. You **MUST** use a Gmail App Password.

## Step-by-Step Guide to Get Gmail App Password

### Step 1: Enable 2-Step Verification
1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Under "Signing in to Google", click on **"2-Step Verification"**
3. Follow the prompts to enable 2-Step Verification (if not already enabled)
   - You'll need to verify your phone number
   - You may need to enter a verification code sent to your phone

### Step 2: Generate App Password
1. After enabling 2-Step Verification, go back to [Google Account Security](https://myaccount.google.com/security)
2. Under "Signing in to Google", click on **"App passwords"**
   - If you don't see "App passwords", search for it in the search bar
3. You may be asked to sign in again
4. Select:
   - **App**: Mail
   - **Device**: Other (Custom name)
   - **Name**: Enter "NutriKid System" or any name you prefer
5. Click **"Generate"**
6. Google will show you a **16-character password** (it looks like: `abcd efgh ijkl mnop`)
7. **Copy this password** (you can remove the spaces)

### Step 3: Update .env File
1. Open the `.env` file in your project root
2. Find the line: `MAIL_PASSWORD=Ceejay_cejas123`
3. Replace `Ceejay_cejas123` with the 16-character App Password you just copied
4. Save the file

### Example .env Configuration:
```env
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=true
MAIL_USERNAME=cejasceejay03@gmail.com
MAIL_PASSWORD=abcd efgh ijkl mnop
```

**Note:** Remove spaces from the App Password when pasting it into the .env file.

## Testing Email Configuration

After setting up the App Password, you can test if emails are working by:

1. Creating a new admin account (should send welcome email)
2. Creating a new student account (should send welcome email)
3. Submitting a report as admin (super admins should receive email)

## Troubleshooting

### Error: "Username and Password not accepted"
- Make sure you're using the **App Password**, not your regular Gmail password
- Verify that 2-Step Verification is enabled
- Check that the App Password was copied correctly (no extra spaces)

### Error: "Less secure app access"
- Gmail no longer supports "Less secure app access"
- You **MUST** use App Passwords with 2-Step Verification enabled

### Still having issues?
- Check the server logs for detailed error messages
- Verify your `.env` file is in the project root directory
- Make sure Flask-Mail is installed: `pip install flask-mail`

## Security Notes

- **Never commit your `.env` file to Git** (it should be in `.gitignore`)
- **Never share your App Password** with anyone
- If you suspect your App Password is compromised, revoke it and generate a new one
- App Passwords can be revoked individually without affecting your main Google account password

