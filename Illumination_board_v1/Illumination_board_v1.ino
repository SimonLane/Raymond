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
// 1) Interface with interlock (optoisolated coupler)
// 2) Measure power on photodiode for calibration
// 3) add front panel control for outputs and control switches

#include <SPI.h>
#include <i2c_t3.h>
//SPI
int ResetPin = 33;
int SyncPin  = 34;
int LatchPin = 35;
//Serial
String device = "";
String command1 = "";
String command2 = "";
int serial_part = 0;
bool Verbose = true;
//I2C
void receiveEvent(size_t count);
void requestEvent(void);
#define MEM_LEN 256
char databuf[MEM_LEN];
volatile uint8_t received = 0;

//galvo 1 presets
int visible_on = 3000;
int maitai_on = 1000;
int off_offset = 150;

void setup() {
  pinMode(ResetPin,OUTPUT);
  pinMode(SyncPin, OUTPUT);
  pinMode(LatchPin,OUTPUT);
  digitalWrite(SyncPin, 1);
  digitalWrite(LatchPin,0);
  digitalWrite(ResetPin,1);
  SPI.begin();
  
  Serial.begin(115200);

// Setup for Slave mode, address 0x66, pins 18/19, external pullups, 400kHz
  Wire.begin(I2C_SLAVE, 9, I2C_PINS_18_19, I2C_PULLUP_EXT, 400000);

  memset(databuf, 0, sizeof(databuf));
// register events
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);  
  
  delay(10);
}

class Galvo{
  public:
  bool shutter_open;
  int visible_position;
  int maitai_position;
  int off_position;
  int on_position;
  int pin;
  int off_offset;

  public:
  Galvo(int p, int vp, int mp, int oo){
    visible_position = vp;
    maitai_position = mp;
    pin = p;
    on_position = visible_position;
    off_offset = oo;
    off_position = on_position + off_offset;
  }

  void visible()    { on_position = visible_position;
                    off_position = on_position + off_offset;}
  void maitai()     { on_position = maitai_position;
                    off_position = on_position + off_offset;}
  void toggle()     { if(shutter_open)  {off();}
                    else              {on();}}
  void on()         {analogWrite(pin,on_position);  shutter_open=true;}
  void off()        {analogWrite(pin,off_position); shutter_open=false;}
  void go_to(int p) {analogWrite(pin,p);            shutter_open=true;}
};

class Diode{
  public:
  int wavelength;
  int channel;

  public:
  Diode(int w, int c){
    
  }
};

/////////////////////////////////////////////INSTANSES/////////////////////////////////////////////

Galvo        G1(A21, visible_on, maitai_on, off_offset);


/////////////////////////////////////////////FUNCTIONS/////////////////////////////////////////////

void checkSerial(){
  char rc;
  while (Serial.available()) {
   rc = Serial.read();
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {respond(device,command1,command2); serial_part = 0;}   // ';' char
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
   if (rc == 47)      {serial_part = 1; device = "";command1 = "";command2 = "";}  // '/' char
   else if (rc == 46)      {serial_part += 1;}                                     // '.' char
   else if (rc == 59)      {  respond(device,command1,command2);                   // ';' char
                             serial_part = 0;
                             received = 0;}                     
   else if (serial_part == 1){device   += rc;}
   else if (serial_part == 2){command1 += rc;}
   else if (serial_part == 3){command2 += rc;}
   i++;
 }
}


void respond(String device,String command1, String command2) {
    if(device == "on")          {G1.on();}
    if(device == "off")         {G1.off();}
    if(device == "toggle")      {G1.toggle();}
    
    if(device == "hello")       {Serial.println("Illumination board");}
    if(device == "visible")     {G1.visible();}//galvo 1 stored position for visible laser
    if(device == "maitai")      {G1.maitai();} //galvo 1 stored position for maitai laser
    if(device == "G1")          {G1.go_to(command1.toInt());}
    if(device == "405")         {}
}


void setChannel(int channel, int value){
  digitalWrite(SyncPin, 0);
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE1));
  SPI.transfer(0x30 + channel);
  SPI.transfer(value >> 8);
  SPI.transfer(value & 0xFF);
  SPI.endTransaction();
  digitalWrite(SyncPin, 1);
  if(Verbose){
    Serial.println(0x30 + channel, BIN);
    Serial.println(value >> 8, BIN);
    Serial.println(value & 0xFF, BIN);
  }
}

void receiveEvent(size_t count){
    Wire.read(databuf, count);  // copy Rx data to databuf
    received = count;           // set received flag to count, this triggers print in main loop
}

// handle Tx Event (outgoing I2C data)
void requestEvent(void)   {Wire.write(databuf, MEM_LEN);} // fill Tx buffer (send full mem)

void loop() {
  checkSerial();  
  checkI2C();
}
