///////////
// Done  //
///////////
// SPI functions to set span range and voltages on the DAC board, and a function for galvo control.
// Setting the galvo mirror position
///////////
// TO DO //
///////////
//Test Diodes and add current control boards
//diode driver signal is 0-2.5V --> 0-200mA output
//  + set to 0-5V range and use only first 2047 values (Max 2.5V)
//  + class for laser (can encompas NIRs and Vis?)
//  + needs to be limited eg 780nm Diode  - threshold is 14mA
//                                        - operating 24mA
//                                        - max 40mA
//  + Serial input (computer control from GUI)
//  + I2C input (from main Rayleigh control board)
//  + Interlock
//  + LED indicator

#include <SPI.h>

int chipSelectPin = 10;
int safe_position = 2047; //safe position for the gavlo mirror so neither beam exits the system

void setup() {
  ///////GALVO MIRROR POSITION///////
  analogWriteResolution(12);
                      // min    centre     max
  analogWrite(A22, 0); // 0 <--> 2047 <--> 4095

  // ANALOG BOARD//
  
  pinMode(10, OUTPUT);
  Serial.begin(115200);
  SPI.begin();

  //inital setup of DAC channels  
  setRangeAll(0);//set span all to 0-5V
  setChannelAll(0);//set all channels to 0V
  setRange(8,3);//set channel 8 and 9 span to +-10V
  setRange(9,3);
  setGalvo(2048);//set galvo channels to 0V (centre)
  
  Serial.begin(115200);
  delay(1000);
}

void loop() {
  checkSerial(); 
}

class laser{
  public:
  int wavelength;
  int laserChannel;       // laser channel on DAC (-1 if none)
  int AOTFchannel;        // AOTF channel on DAC (-1 if none)
  int laserSetPoint;      // value for diode driver
  int aotfSetPoint;       // value for AOTF
  int setPoint;           //set point to be used to update the DAC in use
  int state;              // currently on or off     
  float calibration;      // for calculating aproximate laser power (BFP) in mW (mW/volt)
  int control;            // 0: laser only; 1: constant laser, vary AOTF;
  int maxSP;              // maximum value to be applied to the DAC (for power limiting in diode)
  int minSP;              // minimum value to be applied to the DAC (for lasing in diode)
  int channel;            // channel to be used in the control functions
  
  public:
  laser(int w, int lc, int ac, int lsp, int ctrl, float cal, int masp, int misp){
    wavelength = w;
    laserChannel = lc;
    AOTFchannel  = ac;
    laserSetPoint = lsp;
    aotfSetPoint = 0;
    state = 0;
    control = ctrl;      
    calibration = cal;       
    maxSP = masp;
    minSP = misp;
    setPoint = 0; 
  
    if(control == 0){channel = laserChannel;} //NIR and 405
    if(control == 1){channel = AOTFchannel;}  //488, 561, 633
  }

  void laser_warmup(){
    if(control == 1){::setChannel(laserChannel,laserSetPoint);} //set the laser on, to allow warm up
  }
  void toggle() {
    if(state){off();}
    else{on();}
  }
  void on(){::setChannel(channel,setPoint);state = 1;}
  void on(int p){power(p); ::setChannel(channel,setPoint);}
  void off(){::setChannel(channel,0);state = 0;}
  void power(int p){        //TO DO, allow scaling from minSP to maxSP
    //input is %, ouput needs to be 12-bit value, but scaled to laser threshold and laser limit
    setPoint = map(p, 0, 100, minSP, maxSP);
    Serial.println(setPoint);
  }
  
  void report(){
    Serial.print("wavelength:\t\t");Serial.print(wavelength);Serial.println("nm");
    Serial.print("Channel:   \t\t");Serial.println(channel);
    Serial.print("Setpoint:  \t\t");Serial.print(setPoint);
    Serial.print(" (");Serial.print(setPoint/40.0);
    Serial.print("%; ");Serial.print(setPoint*calibration);Serial.println("mW)");
    Serial.print("Status:    \t\t");Serial.println(state);
    Serial.print("Limits:    \t\t");Serial.print(minSP);Serial.print(", ");Serial.print(maxSP);
    Serial.print(" (");Serial.print(minSP*calibration);Serial.print("mW, ");Serial.print(maxSP*calibration);Serial.println("mW)");
  }
};

//~~~~~~~~~~~~~~~~~~~~~~~~~~ Instances ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

//            wav  laser AOTF laser ctrl  cal   max     min
//                 ch    ch   sp    mode        sp      sp

laser   ld405(405, 13,   -1,   0,   0,    1,    4000,   0);
laser   ld488(488, 11,   12,   -1,   0,    1,    4000,   0);
laser   ld561(561, 15,   14,   -1,   0,    1,    4000,   0);
laser   ld660(660, 12,   0,    -1,   0,    1,    4000,   0);
laser   ld780(780, 7,   -1,    0,   0,    1,    2047,   0);

//~~~~~~~~~~~~~~~~~~~~~~~~~~ Serial communications ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
String device = "";
String command1 = "";
String command2 = "";
int serial_part = 0;
bool Verbose = false;

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

void hablar(String parabla){
  if(Verbose == true){Serial.println(parabla);}
}

void respond(String device,String command1, String command2) {
  hablar("Serial in: " + device + '.' + command1 + '.' + command2);
    if(device == "hello")                     {Serial.println("laser controller");}

// diode controls
    if(device == "stop")                      {allOff();hablar("Zero all channels");}
    if(device == "man")                       {setChannel(command1.toInt(),command2.toInt());}
    if(device == "405")                       {setGalvo(1900);ld405.on(command1.toInt());}
    if(device == "488")                       {setGalvo(1900);ld488.on(command1.toInt());}
    if(device == "561")                       {setGalvo(1900);ld561.on(command1.toInt());}
    if(device == "660")                       {setGalvo(1900);ld660.on(command1.toInt());}
    if(device == "780")                       {setGalvo(2100);ld780.on(command1.toInt());}
    if(device == "warmup")                  {//set voltage to the laser, but not to the AOTF
                                        if(command1.toInt()==488){} //ld488.laser_warmup();
                                        if(command1.toInt()==561){} //ld561.laser_warmup();
                                        if(command1.toInt()==660){} //ld660.laser_warmup();
                                              }
    if(device == "report")                    {
                                        if(command1.toInt()==405){ld405.report();} 
                                        if(command1.toInt()==488){ld488.report();} 
                                        if(command1.toInt()==561){ld561.report();} 
                                        if(command1.toInt()==660){ld660.report();}
                                        if(command1.toInt()==780){ld780.report();}
                                              }
                                              
                                              
}

void allOff(){
  setGalvo(safe_position);
  for(int c = 0;  c<8;  c++){setChannel(c,0);}
  for(int c = 10; c<16; c++){setChannel(c,0);}
}

void setGalvo(int value){
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0x0 + 8);                //channel 8 set register, but no update
  SPI.transfer(value >> 4);
  SPI.transfer((value << 4) & 0xFF);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
  value = 4095 - value;                 //invert the value to get bipolar signals
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0x0 + 9);                //channel 9 set register, but no update
  SPI.transfer(value >> 4);
  SPI.transfer((value << 4) & 0xFF);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();

  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0x90);                   //update all channels
  SPI.transfer(value >> 4);
  SPI.transfer((value << 4) & 0xFF);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
}

void setChannel(int channel, int value){
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0x30 + channel);
  SPI.transfer(value >> 4);
  SPI.transfer((value << 4) & 0xFF);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
}

void setRange(int channel, int range){
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0x60 + channel);
  SPI.transfer(0x00);
  SPI.transfer(range);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
}

void setChannelAll(int value){
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0xA0);
  SPI.transfer(value >> 4);
  SPI.transfer((value << 4) & 0xFF);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
}

void setRangeAll(int range){
  SPI.beginTransaction(SPISettings(50000000, MSBFIRST, SPI_MODE0));
  digitalWrite(chipSelectPin, 0);
  SPI.transfer(0xE0);
  SPI.transfer(0x00);
  SPI.transfer(range);
  digitalWrite(chipSelectPin, 1);
  SPI.endTransaction();
}
