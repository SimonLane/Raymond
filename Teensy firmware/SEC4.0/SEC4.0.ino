#include "CRC.h"
#define ETL Serial1
#include <SPI.h>
#include <i2c_t3.h>

#define MEM_LEN 256
char databuf[MEM_LEN];

//definitions, flags etc.

long unsigned prev_t          = 0;
bool scan_when_ready          = false;
bool filter_flag              = false;
bool camera_flag              = false;
bool laser_on_flag            = false;
long unsigned laser_off_time  = 0;
bool z_flag                   = false;
bool y_flag                   = false;
bool in_scan                  = false;
int LEDpin                    = 20;
int laser_trigger_pin         = 36;
const int DNreadyPin          = 35;
const int slaveSelectPin      = 10;
int TriggerPin                = 34; //incoming trigger from Scan Mirror
int filter_pin                = 0; 
int camera_pin                = 0; 
int z_pin                     = 0; 
int y_pin                     = 0; 
int z_separation              = 1;
int z_number                  = 50;
int z_start                   = 0;
int exposure                  = 10;
int LED_status                = 0;

uint8_t laser_board_I2C       = 0x66; // target I2C Slave address


//~~~~~~~~~~~~~~~~~~~~~~~~~~ETL functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

int ETL_offset = 0;
int ETL_position = 0;

void ETL_handshake(){
  int incomingByte;
  ETL_clear_buffer();
  Serial.print("to ETL: Start --> ");
  ETL.print("Start");
  delay(10);
  while (ETL.available() > 0) {
    incomingByte = ETL.read();
    Serial.write(incomingByte);
  }
  Serial.write("\r");
  //Set ETL temperature limits 
  ETL.write(0x50);ETL.write(0x77);ETL.write(0x54);ETL.write(0x41);ETL.write(0x02);ETL.write(0x30);
  ETL.write(0x01);ETL.write(0x40);ETL.write(0x32);ETL.write(0x37);
//set ETL Focal power mode  
  ETL.write(0x4d);ETL.write(0x77);ETL.write(0x43);ETL.write(0x41);ETL.write(0x56);ETL.write(0x76);
}

void ETL_clear_buffer(){while (ETL.available() > 0) {ETL.read();}}

float ETL_Temp(){
  int incomingByte;
  ETL_clear_buffer();
  ETL.print("T");ETL.print("A");ETL.write(0xFE);ETL.write(0xF0);
  int b = 0;
  int t = 0;
  delay(10);
  while (ETL.available() > 0) {
      incomingByte = ETL.read();
      if(b==3){t = t | (incomingByte<<8);}
      if(b==4){t = t | incomingByte;}
      b++;
    }
  return (t * 0.0625);
}


void ETLto(int p){
  ETL_position = p;
  p = p + ETL_offset;
//fp range is 700 to 1700 (-1.5 to 3.5 diopters)
  
  if(p<700 || p>1700){return;} //out of range check
//template command structure, 10 bytes:
  //  P       w       C         A         FH FL   0   0   CS1  CS2
  // "Power"  write   Control   Channel   focus   dummy   checksum
  char focus_output_[10] = {0x50,0x77,0x44,0x41,0x00,0x00,0x00,0x00,0x00,0x00}; 
//add focus bytes
  focus_output_[4] = p >> 8;
  focus_output_[5] = p & 0xFF;
//generate checksum
  uint16_t CS = crc16(focus_output_, 8, 0x8005, 0, 0, true, true); //only use the first 8 bytes
  focus_output_[8] = CS & 0xFF;   //break CS into two bytes, and reverse the order
  focus_output_[9] = CS>>8; 
//write the binary data to the ETL
  for(int i=0;i<10;i++){ETL.write(focus_output_[i]);}
}

void ETLoffset(int OS){
  ETL_offset = OS;
  ETLto(ETL_position);
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ LED functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


void LEDon(){
  digitalWrite(20, HIGH);
  hablar("LED on");
  LED_status = 1;
}

void LEDoff(){
  digitalWrite(20, LOW);
  hablar("LED off");
  LED_status = 0;
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ mirror functions ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~




uint32_t generateSPFPR(float f) {
  float normalized;
  int16_t shift;
  int32_t sign, exponent, significand;
 
  if (f == 0.0){return 0;} //handle this special case
                          //check sign and begin normalization
  if (f < 0) { sign = 1; normalized = -f; } 
  else { sign = 0; normalized = f; }
                          //get normalized form of f and track the exponent
  shift = 0;
  while (normalized >= 2.0) { normalized /= 2.0; shift++; }
  while (normalized < 1.0)  { normalized *= 2.0; shift--; }
  normalized = normalized - 1.0;
                          //calculate binary form (non-float) of significand 
  significand = normalized*(0x800000 + 0.5f);
                          //get biased exponent
  exponent = shift + 0x7f; //shift + bias
                          //combine and return
  return (sign<<31) | (exponent<<23) | significand;
}

void sendWriteSPI(uint32_t registers, uint32_t valueX, uint32_t valueY){   // quick function to write 'standard' format commands to the mirror

  while(digitalRead(DNreadyPin) == HIGH){}                         //wait for slave to be ready
  SPI.beginTransaction(SPISettings(4000000, MSBFIRST, SPI_MODE1));
  digitalWrite(slaveSelectPin,LOW);
                           SPI.transfer(0x00);SPI.transfer(0x01);       //write command
  for(int i=24;i>-8;i=i-8){SPI.transfer((registers >> i) & 0xFF);}      //registers
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueX >> i) & 0xFF);}         //X command
  for(int i=24;i>-8;i=i-8){SPI.transfer((valueY >> i) & 0xFF);}         //Y command
  SPI.transfer(0x7e); //delimiter byte
  digitalWrite(slaveSelectPin,HIGH);
  SPI.endTransaction();
  
}

void mirrorGain(int gY, int gZ){
  //gains received as ints for convenience of sending over serial protocol
  //convert to floats and invert, as gains required are always < 1
  sendWriteSPI(0x98009900,generateSPFPR(float(1.0/gY)),generateSPFPR(float(1.0/gZ)));
}

void mirrorOffset(int osY, int osZ){
  //conditioning to make sure Y,Z are in range
  sendWriteSPI(0x98019901,generateSPFPR(float(osY)),generateSPFPR(float(osZ)));
}


void mirrorTo(float pY, float pZ){
  // -1.0 -- 1.0 range
  //conditioning to make sure Y,Z are in range
  Serial.print(pY);Serial.print(" ");Serial.println(pZ);
  sendWriteSPI(0x50025102,generateSPFPR(pY),generateSPFPR(pZ));
}
//~~~~~~~~~~~~~~~~~~~~~~~~~~ Laser board communication ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


//timing
void laser_trigger(int d){ //pulse duration (us), sets timer for laser to stay on
  laser_off_time = micros() + d;
  digitalWrite(laser_trigger_pin,1);
  laser_on_flag = true;
}

void checkLaser(){ //gets checked continuously in main loop to turn laser off once timer expires
  if(laser_on_flag){
    if(micros() > laser_off_time){
      digitalWrite(laser_trigger_pin,0);
      laser_on_flag = false;
    }
  }
}
// communication over I2C

void set_laser(int w,int p){ //wavelength and power to be used
  Wire1.beginTransmission(laser_board_I2C);
  Wire1.write("/");
  Wire1.write(w);
  Wire1.write(".");
  Wire1.write(p);
  Wire1.write(";");
  Wire1.endTransmission();           // Transmit to Slave

  // Check if error occured
  if(Wire1.getError())
      Serial.print("I2C comm FAIL\n");
  else
      Serial.print("I2C comm OK\n");
}

void test_I2C(){
  Wire1.beginTransmission(laser_board_I2C);
  Wire1.write("/I2Ctest;/stop;");
  Wire1.endTransmission();           // Transmit to Slave

  // Check if error occured
  if(Wire1.getError())
      Serial.print("I2C comm FAIL\n");
  else
      Serial.print("I2C comm OK\n");
}


//~~~~~~~~~~~~~~~~~~~~~~~~~~ Serial communications ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
String device = "";
String command1 = "";
String command2 = "";
String command3 = "";
String command4 = "";
String command5 = "";

int serial_part = 0;
bool Verbose = true;

void checkSerial(){
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {respond(device,command1,command2,command3,command4,command5); serial_part = 0;}   // ';' char
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
   else if (serial_part == 4){command3 += rc;}
   else if (serial_part == 5){command4 += rc;}
   else if (serial_part == 6){command5 += rc;}
 }
}

void hablar(String parabla){
  if(Verbose == true){Serial.println(parabla);}
}

void respond(String device,String command1, String command2, String command3, String command4, String command5) {
    if(device == "hello")                         {Serial.println("Raymond Driver Board");}
// Scan command
    if(device == "S")                             {
        scan_when_ready = true;
        setFilter(command1.toInt()); filter_flag = false;
        exposure        = command2.toInt();
        z_start         = command3.toInt();
        setZ(z_start); z_flag = false;
        z_number        = command4.toInt();
        z_separation    = command5.toInt(); 
    }//Scan command
// Illumination controls    
    if(device == "LEDon")                         {LEDon();}
    if(device == "LEDoff")                        {LEDoff();}

// ETL controls
    if(device == "ETLoffset")                     {ETLoffset(command1.toInt());hablar("ETL offset");}
    if(device == "ETLto")                         {ETLto(command1.toInt());hablar("ETL move");}
  
// mirror controls - to do
    if(device == "Yto")                           {}
    if(device == "Zto")                           {}
    if(device == "Yoffset")                       {}
    if(device == "Zoffset")                       {}
    if(device == "Ygain")                         {}
    if(device == "Zgain")                         {}

//testing
    if(device == "testI2C") {test_I2C();}
   
}

//  ~~~~~~~~~~~~~~~~~~~~~~~~~~ setup ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
void setup() {
  Serial.begin(115200);
  pinMode(20,OUTPUT);
  ETL.begin(38400); 
  delay(100);
  ETL_handshake();
  //mirror_handshake(); //TO DO 
  pinMode(slaveSelectPin,OUTPUT);
  pinMode(DNreadyPin,OUTPUT);
  pinMode(TriggerPin,INPUT); //incoming trigger from Scan Mirror

// Setup for I2C Master mode, pins 37/38, external pullups, 400kHz, 200ms default timeout
  Wire1.begin(I2C_MASTER, 0x00, I2C_PINS_37_38, I2C_PULLUP_EXT, 400000);
  Wire1.setDefaultTimeout(200000); // 200ms
  memset(databuf, 0, sizeof(databuf));
  pinMode(laser_trigger_pin,OUTPUT);
  
}

//~~~~~~~~~~~~~~~~~~~~~~~~~~ main loop ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
float y=0.0;
void loop() {
  checkSerial();
  checkLaser();   //check if laser should be on
//  if(scan_when_ready){ //scan command received and hardware set in motion. 
                       //Monitor until all devices signal they are ready
//    if(digitalRead(filter_pin)) {filter_flag = true;}
//    if(digitalRead(camera_pin)) {camera_flag = true;}
//    if(digitalRead(laser_pin))  {laser_flag = true;}
//    if(digitalRead(z_pin))      {z_flag = true;}
//    if(digitalRead(y_pin))      {y_flag = true;}
//    }

}


void setZ(int z){}//to do, set Z position on ETL
void setFilter(int f){}//to do, set Filter position on illumination board
