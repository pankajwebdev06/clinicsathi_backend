"""
OTP Service for SMS (Fast2SMS), WhatsApp, and Email
"""
import os
import requests
from typing import Optional
from datetime import datetime


class OTPService:
    """Send OTP via SMS, WhatsApp, or Email"""
    
    @staticmethod
    def send_sms_otp(phone_number: str, otp: str) -> bool:
        """
        Send OTP via Fast2SMS (India)
        
        1. Register at https://www.fast2sms.com/
        2. Get API Key from Dashboard
        3. Add to environment: FAST2SMS_API_KEY=your_key
        """
        api_key = os.getenv("FAST2SMS_API_KEY")
        if not api_key:
            print("⚠️ FAST2SMS_API_KEY not set. Skipping SMS.")
            return False
        
        # Clean phone number
        phone = phone_number.replace("+", "").replace(" ", "")
        if len(phone) == 10:
            phone = "91" + phone  # Add India country code
        
        try:
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = {
                "route": "q",  # Quick SMS route
                "message": f"Your ClinicSathi login OTP is: {otp}. Valid for 5 minutes. Do not share this code.",
                "language": "english",
                "flash": 0,
                "numbers": phone,
            }
            headers = {
                "authorization": api_key,
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            result = response.json()
            
            if result.get("return"):
                print(f"✅ SMS sent to {phone}")
                return True
            else:
                print(f"❌ SMS failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ SMS error: {e}")
            return False
    
    @staticmethod
    def send_whatsapp_otp(phone_number: str, otp: str) -> bool:
        """
        Send OTP via WhatsApp Business API (Meta/Facebook)
        
        1. Create Meta Developer Account: https://developers.facebook.com/
        2. Setup WhatsApp Business API
        3. Get Phone Number ID and Access Token
        4. Add to environment:
           - WHATSAPP_PHONE_NUMBER_ID=123456789
           - WHATSAPP_ACCESS_TOKEN=your_token
        """
        phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
        access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
        
        if not phone_id or not access_token:
            print("⚠️ WhatsApp credentials not set. Skipping WhatsApp.")
            return False
        
        # Clean phone number
        phone = phone_number.replace("+", "").replace(" ", "")
        if not phone.startswith("91") and len(phone) == 10:
            phone = "91" + phone
        
        try:
            url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": phone,
                "type": "template",
                "template": {
                    "name": "clinicsathi_otp",  # Create this template in Meta
                    "language": {"code": "en"},
                    "components": [
                        {
                            "type": "body",
                            "parameters": [
                                {"type": "text", "text": otp},
                                {"type": "text", "text": "5"}
                            ]
                        }
                    ]
                }
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            result = response.json()
            
            if "messages" in result:
                print(f"✅ WhatsApp sent to {phone}")
                return True
            else:
                print(f"❌ WhatsApp failed: {result}")
                return False
                
        except Exception as e:
            print(f"❌ WhatsApp error: {e}")
            return False
    
    @staticmethod
    def send_email_otp(email: str, otp: str, name: str = "") -> bool:
        """
        Send OTP via Email using SendGrid
        
        1. Register at https://sendgrid.com/
        2. Create API Key
        3. Verify sender email
        4. Add to environment: SENDGRID_API_KEY=your_key
        """
        api_key = os.getenv("SENDGRID_API_KEY")
        sender_email = os.getenv("SENDER_EMAIL", "noreply@clinicsathi.in")
        
        if not api_key:
            print("⚠️ SENDGRID_API_KEY not set. Skipping Email.")
            return False
        
        try:
            url = "https://api.sendgrid.com/v3/mail/send"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "personalizations": [
                    {
                        "to": [{"email": email}],
                        "subject": "ClinicSathi Login OTP"
                    }
                ],
                "from": {"email": sender_email, "name": "ClinicSathi"},
                "content": [
                    {
                        "type": "text/html",
                        "value": f"""
                        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                            <h2 style="color: #2563eb;">ClinicSathi Login</h2>
                            <p>Hello {name or 'there'},</p>
                            <p>Your login OTP is:</p>
                            <div style="background: #f3f4f6; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 10px; margin: 20px 0;">
                                {otp}
                            </div>
                            <p>This OTP is valid for <strong>5 minutes</strong>.</p>
                            <p style="color: #dc2626; font-size: 12px;">Do not share this code with anyone.</p>
                            <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 20px 0;">
                            <p style="color: #6b7280; font-size: 12px;">
                                If you didn't request this OTP, please ignore this email.<br>
                                ClinicSathi - Your Digital Clinic Assistant
                            </p>
                        </div>
                        """
                    }
                ]
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            
            if response.status_code == 202:
                print(f"✅ Email sent to {email}")
                return True
            else:
                print(f"❌ Email failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Email error: {e}")
            return False
    
    @staticmethod
    def send_otp_all(phone: str, email: Optional[str], otp: str, name: str = "") -> dict:
        """
        Send OTP via all available channels
        Returns status of each channel
        """
        results = {
            "sms": False,
            "whatsapp": False,
            "email": False,
            "demo": True  # Always return OTP for now
        }
        
        # Try SMS
        results["sms"] = OTPService.send_sms_otp(phone, otp)
        
        # Try WhatsApp
        results["whatsapp"] = OTPService.send_whatsapp_otp(phone, otp)
        
        # Try Email if provided
        if email:
            results["email"] = OTPService.send_email_otp(email, otp, name)
        
        return results


# Simple function for auth router
def send_otp_to_user(phone: str, email: Optional[str], otp: str, name: str = "") -> dict:
    """Send OTP to user via all available channels"""
    return OTPService.send_otp_all(phone, email, otp, name)
