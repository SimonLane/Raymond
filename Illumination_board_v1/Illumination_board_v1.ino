// Control board utilizing EVAL-AD5679RSDZ
// Simon Lane 2022

// inputs
// 1) Receive commands over USB (from laser GUI on PC, or from main microscope GUI when 'free-imaging)
// 2) Receive commands from microscope controller over I2C duing an acquisition

// outputs
// 1) Galvo 1. select laser input, visible, NIR diode bank, MaiTai
// 2) Galvo 2. select within the NIR diode bank
// 3) Drive Analog Device board over SPI - Control 405nm diode
//                                         - Control 660nm diode
//                                         - Control thorlabs laser diode drivers for NIR wavelengths
//                                         - Control AOTF for 488, 563 & 660nm power

// To Do
// 0) Software reset analog output board in setup (restart teensy ==> reset all analog channels to 0V)
// 1) Interface with interlock (optoisolated coupler)
// 2) Measure power on photodiode for calibration
// 3) add front panel control for outputs and control switches

#include <SPI.h>
#include <i2c_t3.h>

//Mode  -  who con control the illumination board? 
              // Always         - Serial port (from python script) 
              // Sometimes      - I2C and trigger line (the microscope control board)
int mode = 0; // 0 - Serial only; 1 - I2C and Serial

//SPI
bool verbose = false; // computer control over serial - handshake won't work in verbose mode
int ResetPin = 33;
int SyncPin  = 34;
int LatchPin = 35;
//Serial
String device = "";
String command1 = "";
String command2 = "";
int serial_part = 0;

//I2C
void receiveEvent(size_t count);
void requestEvent(void);
#define MEM_LEN 256
char databuf[MEM_LEN];
volatile uint8_t received = 0;

// Trigger Pins
int Trigger_IN  = 23;
int Trigger_OUT = 22;
int Trigger_3   = 21;

int active_wavelength;
int shutter_open = 0;
int shutter_close = 0;
int safe_position = 2000;
void respond(String,String,String);
void setChannel(int, int);

class Laser{
  public:
  int wavelength;
  int analog_channel;
  int digital_channel;
  int minimum;
  int maximum;
  float calibration;
  int galvo_on; //position
  int galvo_off;//position
  int galvo_pin;
  int power_value;
  int power_percentage;
  

  public:
  Laser(int wav, int ach, int dch, int mi, int ma, int cal, int gon, int goff){
    wavelength = wav;
    analog_channel = ach;
    digital_channel = dch;
    minimum = mi;
    maximum = ma;
    calibration = cal;
    galvo_on = gon;
    galvo_off = goff;
    galvo_pin = A21;
    power_percentage = 0;
    power_value = 0;  //2^16
    if(digital_channel > 0){
      pinMode(digital_channel,OUTPUT);
      digitalWrite(digital_channel,0);
    }
  }

  void trigger(int d){
    if(wavelength == ::active_wavelength){
      if(::mode == 1){ //trigger only active when controlled by the microscope control board
        if(digital_channel > 0){digitalWrite(digital_channel,d);}   //exclude 405
        else{analogWrite(analog_channel,power_value * d);}          //405 only
      }
    }
  }

  void power(int p){
    power_percentage = p;
    power_value = map(p,0,100,minimum,maximum);
    
    if(p==0 and digital_channel!=-1){digitalWrite(digital_channel,0);}//turn off digital
//if active wavlength not this wavelength, then turn off active_wavelength (analog and digital)
    if(wavelength != ::active_wavelength){respond(String(active_wavelength),"0","");}
//make this wavelength the active wavelength
    ::active_wavelength = wavelength;

// if mode == 0 (command from PC) then set laser, power and galvo 'on'
// if mode == 1 then set active laser and power to the AOTF(analog), set galvo, don't set AOTF(digital) on 
//allow digital to be driven by the trigger input
    analogWrite(galvo_pin,galvo_on);                //set galvo
    ::setChannel(analog_channel,power_value);       //set analog
    if(mode==0){digitalWrite(digital_channel,0);}   //set digital if mode 0

    if(verbose){
      Serial.print("mode: ");             Serial.print(mode);
      Serial.print(". set ");             Serial.print(wavelength);
      Serial.print("nm laser power to "); Serial.print(power_value);
      Serial.print(" (");                 Serial.print(power_percentage);
      Serial.println("%)");
    }
  }
};

/////////////////////////////////////////////INSTANSES/////////////////////////////////////////////

// array holding the Laser objects
        


                //wav  dig  ana  min  max     cal   gOn   goff
Laser        L405(405, -1,  8,   0,   65535,  1,    1000, 1100);
Laser        L488(488, 29,  9,   0,   65535,  1,    1000, 1100);
Laser        L561(561, 30,  10,  0,   65535,  1,    1000, 1100);
Laser        L660(660, 31,  11,  0,   65535,  1,    1000, 1100);
Laser        L780(780, 17,  0,   0,   32767,  1,    2000, 2100);





//interrupt CHANGE
void trigger_function(){
  int d = digitalRead(Trigger_IN);
    L405.trigger(d);
    L488.trigger(d);
    L561.trigger(d);
    L660.trigger(d);
    L780.trigger(d);
}

void setup() {
//SPI
  pinMode(ResetPin,OUTPUT);
  pinMode(SyncPin, OUTPUT);
  pinMode(LatchPin,OUTPUT);
  digitalWrite(SyncPin, 1);
  digitalWrite(LatchPin,0);
  digitalWrite(ResetPin,1);
  SPI.begin();
//Galvos
  pinMode(A21,OUTPUT);
  pinMode(A22,OUTPUT);
  analogWriteResolution(12);
  analogWrite(A21,safe_position);
//AOTF
  pinMode(31,OUTPUT);
  pinMode(30,OUTPUT);
  pinMode(29,OUTPUT);
//Serial - USB
  Serial.begin(115200);
// I2C
  Wire.begin(I2C_SLAVE, 0x66, I2C_PINS_18_19, I2C_PULLUP_EXT, 400000);
  memset(databuf, 0, sizeof(databuf));
// register events
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);  
// Triggers
  pinMode(Trigger_IN, INPUT_PULLUP); 
  pinMode(Trigger_OUT, OUTPUT);  
  digitalWrite(Trigger_OUT,1);
  attachInterrupt(digitalPinToInterrupt(Trigger_IN), trigger_function, CHANGE);

  delay(10);
}
/////////////////////////////////////////////FUNCTIONS/////////////////////////////////////////////



void checkSerial(){
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {                                                       // ';' char
                             if(verbose){Serial.print("Over Serial: ");}
                             respond(device,command1,command2); 
                             serial_part = 0;}
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
 }
}

void checkI2C(){
  char rc;
  int i=0;
  while (received) {
    
   rc = databuf[i];
   if(rc == 0)              {break;}                                                    //null char
   if (rc == 47)            {serial_part = 1; device = "";command1 = "";command2 = "";} // '/' char
   else if (rc == 46)       {serial_part += 1;}                                         // '.' char
   else if (rc == 59)       {                                                           // ';' char
                             if(verbose){Serial.print("Over I2C: ");}
                             respond(device,command1,command2);
                             serial_part = 0;
                             received = 0;}                     
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
   i++;
 }
}


void respond(String device,String command1, String command2) {
    if(verbose){Serial.print(device);Serial.print(" ");Serial.print(command1);Serial.print(" ");Serial.println(command2); }
    if(device == "stop")        {analogWrite(A21,shutter_close);setAlltoZero();}       
    if(device == "405")         {L405.power(command1.toInt());}     
    if(device == "488")         {L488.power(command1.toInt());}
    if(device == "561")         {L561.power(command1.toInt());}
    if(device == "660")         {L660.power(command1.toInt());}
    if(device == "780")         {L780.power(command1.toInt());}
    
    if(device == "mode")        {mode = command1.toInt();}                             
    if(device == "G1")           {analogWrite(A21,command1.toInt());} //for manually setting the galvo (tuning etc.)
    if(device == "G2")           {         //for manually setting the galvo (tuning etc.)
                                 analogWrite(A22,command1.toInt());
                                 //Serial.println(command1.toInt());
                                }                            
    if(device == "D")           {digitalWrite(command1.toInt(),command2.toInt());} //For manually turning on/off digital pins
    if(device == "A")           {setChannel(command1.toInt(),command2.toInt());} //For manually turning on/off digital pins
    
    if(device == "verbose")     {if(command1.toInt()==1){verbose = true;}       
                                 if(command1.toInt()==0){verbose = false;}}
    if(device == "hello")       {Serial.println("lasers");}       //handshake                     
}


void setChannel(int channel, int value){
  digitalWrite(SyncPin, 0);
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE1));
  SPI.transfer(0x30 + channel);
  SPI.transfer(value >> 8);
  SPI.transfer(value & 0xFF);
  SPI.endTransaction();
  digitalWrite(SyncPin, 1);
  if(verbose){
    Serial.println(0x30 + channel, BIN);
    Serial.println(value >> 8, BIN);
    Serial.println(value & 0xFF, BIN);
  }
}

void setAlltoZero(){
  digitalWrite(SyncPin, 0);
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE1));
  SPI.transfer(0xB0 );
  SPI.transfer(0x00);
  SPI.transfer(0x00);
  SPI.endTransaction();
  digitalWrite(SyncPin, 1);
  if(verbose){
    Serial.println(0xB0, BIN);
    Serial.println(0x00, BIN);
    Serial.println(0x00, BIN);
  }
//for(int i=0;i<16;i++){setChannel(i,0);}//alternative method
}

void receiveEvent(size_t count){
    Wire.read(databuf, count);  // copy Rx data to databuf
    received = count;           // set received flag to count, this triggers events in main loop
}

// handle Tx Event (outgoing I2C data)
void requestEvent(void)   {Wire.write(databuf, MEM_LEN);} // fill Tx buffer (send full mem)

void loop() {
  checkSerial();  
  if(mode == 1) {checkI2C();}
}
